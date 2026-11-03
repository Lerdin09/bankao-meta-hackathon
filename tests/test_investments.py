"""
Módulo de Investimentos: catálogo, subscrição, registo externo, sincronização com o
fornecedor, alertas de vencimento, histórico e resgates (total, parcial, externo).
"""
import datetime
import uuid

from fastapi.testclient import TestClient

from backend.database.connection import transaction_scope
from backend.main import app
from backend.providers.investments import fetch_update
from backend.services.ledger import post_investment_movement

client = TestClient(app)


def _user():
    email = f"inv_{uuid.uuid4().hex[:8]}@bankao.ao"
    r = client.post("/api/auth/register", json={
        "email": email, "telefone": "+244923" + str(uuid.uuid4().int)[:6],
        "password": "Teste12345", "confirm_password": "Teste12345", "terms_accepted": True})
    assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    aoa = next(a for a in client.get("/api/accounts", headers=h).json() if a["currency"] == "AOA")
    with transaction_scope() as conn:  # saldo inicial via livro-razão
        post_investment_movement(conn=conn, account_id=aoa["id"], amount_minor=500_000_000,
                                 idempotency_key="f_" + uuid.uuid4().hex, description="saldo de teste",
                                 tx_type="investment_redeem")
    return h, aoa


def _bal(h):
    return next(a for a in client.get("/api/accounts", headers=h).json() if a["currency"] == "AOA")["balance_decimal"]


def test_catalog_shape_and_filters():
    d = client.get("/api/investments/catalog").json()
    assert d["total_count"] == len(d["products"]) >= 4
    assert {"rate_annual", "term_label", "min_amount", "risk_level", "fees_info", "redemption_conditions"} <= set(d["products"][0])
    etfs = client.get("/api/investments/catalog", params={"category": "etf"}).json()["products"]
    assert etfs and all(p["category"] == "etf" for p in etfs)
    det = client.get(f"/api/investments/catalog/{d['products'][0]['id']}").json()
    assert len(det["simulations"]) == 4


def test_apply_below_minimum_is_rejected():
    h, aoa = _user()
    p = next(p for p in client.get("/api/investments/catalog").json()["products"] if p["currency"] == "AOA")
    r = client.post("/api/investments/portfolio/apply", headers=h,
                    json={"product_id": p["id"], "amount": 1, "account_id": aoa["id"]})
    assert r.status_code == 400


def test_full_flow_apply_external_sync_alerts_redeem():
    h, aoa = _user()
    p = next(p for p in client.get("/api/investments/catalog").json()["products"] if p["currency"] == "AOA")
    before = _bal(h)
    amount = p["min_amount"] * 2
    assert client.post("/api/investments/portfolio/apply", headers=h,
                       json={"product_id": p["id"], "amount": amount, "account_id": aoa["id"]}).status_code == 200
    assert _bal(h) == before - amount

    today = datetime.date.today()
    ext = client.post("/api/investments/portfolio/external", headers=h, json={
        "name": "Obrigações BFA", "category": "obrigacoes", "institution": "BFA", "amount": 800000,
        "rate_annual": 17, "start_date": (today - datetime.timedelta(days=120)).isoformat(),
        "maturity_date": (today + datetime.timedelta(days=10)).isoformat()})
    assert ext.status_code == 200
    # investimento externo não mexe no saldo
    assert _bal(h) == before - amount

    sync = client.post("/api/investments/portfolio/sync-all", headers=h).json()
    assert sync["synced_count"] == 2 and sync["failed_count"] == 0

    port = client.get("/api/investments/portfolio", headers=h).json()
    s = port["summary"]
    assert s["active_count"] == 2 and s["total_yield_aoa"] > 0 and s["total_current_aoa"] > s["total_invested_aoa"]
    assert s["next_maturity_name"] == "Obrigações BFA"
    assert len(port["evolution"]) == 6 and port["evolution"][-1]["value_aoa"] >= port["evolution"][-1]["invested_aoa"]

    types = {n["type"] for n in client.get("/api/investments/notifications", headers=h).json()}
    assert {"vencimento_proximo", "rendimento_creditado"} <= types
    # alertas de vencimento não se duplicam
    n1 = len(client.get("/api/investments/notifications", headers=h).json())
    n2 = len(client.get("/api/investments/notifications", headers=h).json())
    assert n1 == n2

    ops = {o["operation_type"] for o in client.get("/api/investments/operations", headers=h).json()}
    assert {"aplicacao", "aplicacao_externa", "juros_dividendo"} <= ops

    inv = {i["is_external"]: i for i in port["investments"]}
    # dar baixa a um externo não credita a conta
    mid = _bal(h)
    assert client.post(f"/api/investments/portfolio/{inv[True]['id']}/redeem", headers=h,
                       json={"account_id": aoa["id"]}).json()["status"] == "resgatado"
    assert _bal(h) == mid
    # resgate parcial BankAO credita a conta
    r = client.post(f"/api/investments/portfolio/{inv[False]['id']}/redeem", headers=h,
                    json={"amount": 50000, "account_id": aoa["id"]}).json()
    assert r["status"] == "ativo" and _bal(h) == mid + 50000


def test_provider_is_deterministic_per_day():
    inv = {"id": "x", "category": "etf", "amount_invested_minor": 1_000_000, "current_value_minor": 1_000_000,
           "start_date": "2026-01-01", "rate_annual": 0}
    d = datetime.date(2026, 11, 2)
    assert fetch_update(inv, "bodiva", d).new_value_minor == fetch_update(inv, "bodiva", d).new_value_minor


def _backdate(inv_id, start, maturity):
    with transaction_scope() as conn:
        conn.execute("UPDATE user_investments SET start_date = ?, maturity_date = ? WHERE id = ?",
                     (start, maturity, inv_id))


def test_matured_investment_is_settled_once_and_credits_account():
    h, aoa = _user()
    p = next(p for p in client.get("/api/investments/catalog").json()["products"]
             if p["currency"] == "AOA" and p["category"] in ("deposito_prazo", "obrigacoes"))
    amount = p["min_amount"] * 2
    assert client.post("/api/investments/portfolio/apply", headers=h,
                       json={"product_id": p["id"], "amount": amount, "account_id": aoa["id"]}).status_code == 200
    after_apply = _bal(h)
    inv = client.get("/api/investments/portfolio", headers=h).json()["investments"][0]
    today = datetime.date.today()
    mat = today - datetime.timedelta(days=5)
    start = mat - datetime.timedelta(days=100)
    _backdate(inv["id"], start.isoformat(), mat.isoformat())

    # juros fixados à data de vencimento (100 dias), não até hoje
    expected_yield = round(inv["amount_invested_minor"] * inv["rate_annual"] / 100.0 * 100 / 365.0)
    port = client.get("/api/investments/portfolio", headers=h).json()
    item = port["investments"][0]
    assert item["status"] == "vencido"
    assert abs(item["accumulated_yield_minor"] - expected_yield) <= 1
    assert port["summary"]["active_count"] == 0
    credited = _bal(h) - after_apply
    assert abs(credited - (amount + expected_yield / 100.0)) < 0.02

    # idempotente: consultar/sincronizar/notificações de novo não credita nem duplica
    client.get("/api/investments/portfolio", headers=h)
    client.post("/api/investments/portfolio/sync-all", headers=h)
    notifs = client.get("/api/investments/notifications", headers=h).json()
    client.get("/api/investments/notifications", headers=h)
    assert abs((_bal(h) - after_apply) - credited) < 0.001
    assert sum(1 for n in notifs if n["type"] == "vencimento_liquidado") == 1
    ops = client.get("/api/investments/operations", headers=h).json()
    assert sum(1 for o in ops if o["operation_type"] == "vencimento") == 1
    # já não se pode resgatar nem sincronizar um vencido
    assert client.post(f"/api/investments/portfolio/{inv['id']}/redeem", headers=h, json={}).status_code == 400


def test_matured_external_is_marked_without_touching_balance():
    h, aoa = _user()
    today = datetime.date.today()
    ext = client.post("/api/investments/portfolio/external", headers=h, json={
        "name": "DP Externo", "category": "deposito_prazo", "institution": "BAI", "amount": 500000,
        "rate_annual": 12, "start_date": (today - datetime.timedelta(days=200)).isoformat(),
        "maturity_date": (today - datetime.timedelta(days=1)).isoformat()})
    assert ext.status_code == 200
    before = _bal(h)
    items = client.get("/api/investments/portfolio", headers=h).json()["investments"]
    assert items[0]["status"] == "vencido" and _bal(h) == before
