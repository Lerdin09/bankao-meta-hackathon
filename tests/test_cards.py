"""
Módulo de Cartões: listagem, detalhe, bloqueio/desbloqueio/cancelamento,
definições, criação de cartão virtual, movimentos, despesas e notificações.
"""
import uuid

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.ledger import post_investment_movement
from backend.database.connection import transaction_scope

client = TestClient(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _user():
    email = f"cards_{uuid.uuid4().hex[:8]}@bankao.ao"
    r = client.post("/api/auth/register", json={
        "email": email,
        "telefone": "+244923" + str(uuid.uuid4().int)[:6],
        "password": "Teste12345",
        "confirm_password": "Teste12345",
        "terms_accepted": True
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    return h


def _get_first_card(h) -> dict:
    r = client.get("/api/cards/", headers=h)
    assert r.status_code == 200, r.text
    cards = r.json()["cards"]
    assert len(cards) > 0, "Utilizador deve ter pelo menos um cartão após registo"
    return cards[0]


# ── Testes ────────────────────────────────────────────────────────────────────

def test_list_cards_returns_at_least_one_card():
    """Após registo o utilizador tem um cartão de débito BankAO criado automaticamente."""
    h = _user()
    r = client.get("/api/cards/", headers=h)
    assert r.status_code == 200
    cards = r.json()["cards"]
    assert isinstance(cards, list)
    assert len(cards) >= 1
    card = cards[0]
    assert card["card_type"] == "debit"
    assert card["network"] == "multicaixa"
    assert card["status"] == "active"
    assert len(card["last_four"]) == 4
    assert "daily_limit" in card
    assert "monthly_limit" in card


def test_get_card_detail():
    """Detalhe de um cartão retorna campos completos."""
    h = _user()
    card = _get_first_card(h)
    r = client.get(f"/api/cards/{card['id']}", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == card["id"]
    assert "online_payments" in d
    assert "atm_withdrawals" in d
    assert "credit_available" in d


def test_block_and_unblock_card():
    """Bloquear e desbloquear um cartão funciona corretamente."""
    h = _user()
    card = _get_first_card(h)
    cid = card["id"]

    # Bloquear
    r = client.post(f"/api/cards/{cid}/control", headers=h, json={"action": "block"})
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"

    # Verificar estado
    detail = client.get(f"/api/cards/{cid}", headers=h).json()
    assert detail["status"] == "blocked"

    # Desbloquear
    r2 = client.post(f"/api/cards/{cid}/control", headers=h, json={"action": "unblock"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "active"


def test_cancel_card_is_permanent():
    """Cancelar um cartão é permanente — não pode ser reativado."""
    h = _user()
    card = _get_first_card(h)
    cid = card["id"]

    # Cancelar
    r = client.post(f"/api/cards/{cid}/control", headers=h, json={"action": "cancel", "reason": "teste"})
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    # Tentar desbloquear um cartão cancelado → erro
    r2 = client.post(f"/api/cards/{cid}/control", headers=h, json={"action": "unblock"})
    assert r2.status_code == 400


def test_update_card_settings():
    """Atualizar definições (toggles e limites) do cartão."""
    h = _user()
    card = _get_first_card(h)
    cid = card["id"]

    r = client.patch(f"/api/cards/{cid}/settings", headers=h, json={
        "online_payments": False,
        "international_payments": False,
        "daily_limit_minor": 20_000_000,
        "monthly_limit_minor": 80_000_000,
    })
    assert r.status_code == 200
    updated = r.json()["updated"]
    assert "online_payments" in updated
    assert "daily_limit_minor" in updated

    # Verificar persistência
    detail = client.get(f"/api/cards/{cid}", headers=h).json()
    assert detail["online_payments"] is False
    assert detail["daily_limit_minor"] == 20_000_000


def test_create_virtual_card():
    """Criar um cartão virtual associado a uma conta AOA."""
    h = _user()
    # Obter conta AOA
    accounts = client.get("/api/accounts/", headers=h).json()
    aoa_acc = next((a for a in accounts if a["currency"] == "AOA"), None)
    assert aoa_acc, "Conta AOA deve existir"

    r = client.post("/api/cards/virtual/create", headers=h, json={
        "account_id": aoa_acc["id"],
        "label": "Compras Amazon",
        "single_use": False,
        "spending_limit_minor": 10_000_000,
        "expires_in_days": 180,
    })
    assert r.status_code == 200
    res = r.json()
    assert "card_id" in res
    assert "last_four" in res
    assert len(res["last_four"]) == 4

    # Confirmar que aparece na lista
    cards = client.get("/api/cards/", headers=h).json()["cards"]
    virtual = next((c for c in cards if c["id"] == res["card_id"]), None)
    assert virtual is not None
    assert virtual["is_virtual"] is True
    assert virtual["card_type"] == "virtual"
    assert virtual["label"] == "Compras Amazon"


def test_card_movements_empty_on_new_card():
    """Cartão recém-criado não tem movimentos."""
    h = _user()
    card = _get_first_card(h)
    r = client.get(f"/api/cards/{card['id']}/movements", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "movements" in data
    assert "total" in data
    assert data["total"] == 0


def test_card_spending_summary():
    """Resumo de despesas retorna estrutura correcta."""
    h = _user()
    card = _get_first_card(h)
    r = client.get(f"/api/cards/{card['id']}/spending", headers=h)
    assert r.status_code == 200
    sp = r.json()
    assert "monthly_total" in sp
    assert "by_category" in sp
    assert "daily_evolution" in sp
    assert isinstance(sp["by_category"], list)
    assert isinstance(sp["daily_evolution"], list)


def test_notifications_list_and_read():
    """Criar cartão virtual gera notificação; marcar como lida funciona."""
    h = _user()
    accounts = client.get("/api/accounts/", headers=h).json()
    aoa_acc = next(a for a in accounts if a["currency"] == "AOA")

    # Criar cartão virtual (gera notificação)
    client.post("/api/cards/virtual/create", headers=h, json={
        "account_id": aoa_acc["id"],
        "label": "Teste Notif",
        "expires_in_days": 30,
    })

    notifs_r = client.get("/api/cards/notifications/list", headers=h)
    assert notifs_r.status_code == 200
    data = notifs_r.json()
    assert "notifications" in data
    assert "unread_count" in data
    assert data["unread_count"] >= 1

    # Marcar como lida
    first_unread = next((n for n in data["notifications"] if not n["is_read"]), None)
    assert first_unread is not None
    r2 = client.post(f"/api/cards/notifications/{first_unread['id']}/read", headers=h)
    assert r2.status_code == 200

    # Confirmar
    data2 = client.get("/api/cards/notifications/list", headers=h).json()
    found = next((n for n in data2["notifications"] if n["id"] == first_unread["id"]), None)
    assert found and found["is_read"] is True


def test_cannot_access_other_user_card():
    """Um utilizador não pode aceder ao cartão de outro utilizador."""
    h1 = _user()
    h2 = _user()
    card1 = _get_first_card(h1)
    r = client.get(f"/api/cards/{card1['id']}", headers=h2)
    assert r.status_code == 404


def test_spending_has_extra_stats():
    """Resumo de despesas inclui estatísticas para os cartões de KPI."""
    h = _user()
    card = _get_first_card(h)
    sp = client.get(f"/api/cards/{card['id']}/spending", headers=h).json()
    for key in ("tx_count", "biggest_amount", "avg_daily", "prev_month_total"):
        assert key in sp


def test_mark_all_notifications_read():
    """Marcar todas como lidas deixa unread_count a zero."""
    h = _user()
    card = _get_first_card(h)
    client.post("/api/cards/virtual/create", headers=h, json={
        "account_id": card["account_id"], "label": "Teste"})
    r = client.post("/api/cards/notifications/read-all", headers=h)
    assert r.status_code == 200
    assert client.get("/api/cards/notifications/list", headers=h).json()["unread_count"] == 0

