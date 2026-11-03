"""
Contactos: pessoas e IBANs do histórico de transferências + contactos guardados (apelido/favorito).
"""
import uuid

from fastapi.testclient import TestClient

from backend.database.connection import transaction_scope
from backend.main import app
from backend.services.iban import gerar_iban_ficticio
from backend.services.ledger import post_investment_movement

client = TestClient(app)


def _user(balance_minor=500_000_000):
    email = f"ct_{uuid.uuid4().hex[:8]}@bankao.ao"
    r = client.post("/api/auth/register", json={
        "email": email, "telefone": "+244923" + str(uuid.uuid4().int)[:6],
        "password": "Teste12345", "confirm_password": "Teste12345", "terms_accepted": True})
    assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    aoa = next(a for a in client.get("/api/accounts", headers=h).json() if a["currency"] == "AOA")
    if balance_minor:
        with transaction_scope() as conn:
            post_investment_movement(conn=conn, account_id=aoa["id"], amount_minor=balance_minor,
                                     idempotency_key="f_" + uuid.uuid4().hex, description="saldo de teste",
                                     tx_type="investment_redeem")
    return h, aoa


def _send(h, src, dest_account_number, amount=1000):
    r = client.post("/api/transfers/internal", headers=h, json={
        "from_account_id": src["id"], "to_account_number": dest_account_number,
        "amount": amount, "idempotency_key": "k_" + uuid.uuid4().hex})
    assert r.status_code == 200, r.text


def test_empty_for_new_user():
    h, _ = _user(0)
    assert client.get("/api/contacts", headers=h).json() == {"contacts": [], "total": 0}


def test_sent_and_received_appear_as_suggested_contacts():
    ha, a = _user()
    hb, b = _user()
    _send(ha, a, b["account_number"], 1000)
    _send(ha, a, b["account_number"], 2000)

    mine = client.get("/api/contacts", headers=ha).json()["contacts"]
    assert len(mine) == 1
    c = mine[0]
    assert c["kind"] == "internal" and c["account_number"] == b["account_number"]
    assert c["sent_count"] == 2 and c["received_count"] == 0 and c["saved"] is False
    assert c["last_sent_amount"] == 2000 and c["last_direction"] == "sent"
    assert "email" not in c

    theirs = client.get("/api/contacts", headers=hb).json()["contacts"]
    assert len(theirs) == 1 and theirs[0]["received_count"] == 2 and theirs[0]["sent_count"] == 0


def test_save_favorite_nickname_and_search():
    ha, a = _user()
    hb, b = _user()
    _send(ha, a, b["account_number"])
    r = client.post("/api/contacts", headers=ha, json={
        "kind": "internal", "account_number": b["account_number"], "nickname": "Mana", "favorite": True})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["saved"] and c["favorite"] and c["display_name"] == "Mana" and c["sent_count"] == 1

    # guardar de novo não duplica
    client.post("/api/contacts", headers=ha, json={"kind": "internal", "account_number": b["account_number"]})
    items = client.get("/api/contacts", headers=ha).json()["contacts"]
    assert len(items) == 1 and items[0]["nickname"] == "Mana"

    assert client.get("/api/contacts", headers=ha, params={"q": "mana"}).json()["total"] == 1
    assert client.get("/api/contacts", headers=ha, params={"q": "zzzz"}).json()["total"] == 0

    p = client.patch(f"/api/contacts/{c['id']}", headers=ha, json={"favorite": False, "nickname": "Irmã"})
    assert p.status_code == 200 and p.json()["favorite"] is False and p.json()["display_name"] == "Irmã"


def test_delete_returns_to_suggested_and_is_private():
    ha, a = _user()
    hb, b = _user()
    _send(ha, a, b["account_number"])
    c = client.post("/api/contacts", headers=ha, json={"kind": "internal", "account_number": b["account_number"]}).json()
    # outro utilizador não mexe no contacto
    assert client.delete(f"/api/contacts/{c['id']}", headers=hb).status_code == 404
    assert client.patch(f"/api/contacts/{c['id']}", headers=hb, json={"favorite": True}).status_code == 404
    assert client.delete(f"/api/contacts/{c['id']}", headers=ha).status_code == 200
    items = client.get("/api/contacts", headers=ha).json()["contacts"]
    assert len(items) == 1 and items[0]["saved"] is False  # o histórico continua a sugeri-lo


def test_iban_contact_validation_and_history():
    h, a = _user()
    iban = gerar_iban_ficticio("AO")
    assert client.post("/api/contacts", headers=h, json={"kind": "iban", "iban": "AO00123", "name": "Zé Maria"}).status_code == 422
    assert client.post("/api/contacts", headers=h, json={"kind": "iban", "iban": iban}).status_code == 422  # sem nome
    ok = client.post("/api/contacts", headers=h, json={"kind": "iban", "iban": iban, "name": "Zé Maria", "nickname": "Zé"})
    assert ok.status_code == 200 and ok.json()["iban"] == iban and ok.json()["sent_count"] == 0

    # IBAN próprio é recusado
    own = client.post("/api/contacts", headers=h, json={"kind": "iban", "iban": a["iban_virtual"], "name": "Eu Mesmo"})
    assert own.status_code in (400, 422)


def test_cannot_save_own_or_unknown_account():
    h, a = _user(0)
    assert client.post("/api/contacts", headers=h, json={"kind": "internal", "account_number": a["account_number"]}).status_code == 400
    assert client.post("/api/contacts", headers=h, json={"kind": "internal", "account_number": "000000"}).status_code == 404


def test_history_pages_balances_and_privacy():
    ha, a = _user()
    hb, b = _user()
    for _ in range(12):
        _send(ha, a, b["account_number"], 1000)
    _send(hb, b, a["account_number"], 500)   # b devolve

    key = client.get("/api/contacts", headers=ha).json()["contacts"][0]["key"]
    p1 = client.get("/api/contacts/history", headers=ha, params={"key": key, "limit": 10, "offset": 0}).json()
    p2 = client.get("/api/contacts/history", headers=ha, params={"key": key, "limit": 10, "offset": 10}).json()
    assert p1["total"] == 13 and len(p1["items"]) == 10 and len(p2["items"]) == 3
    assert p1["has_more"] is True and p2["has_more"] is False
    assert len({i["id"] for i in p1["items"] + p2["items"]}) == 13          # sem repetidas

    newest = p1["items"][0]
    assert newest["direction"] == "received" and newest["amount"] == 495.0   # 500 menos 1% de taxa
    assert newest["balance_after"] == round(newest["balance_before"] + 495.0, 2)
    sent = p1["items"][1]
    assert sent["direction"] == "sent" and sent["amount"] == 1000.0
    assert sent["balance_after"] == round(sent["balance_before"] - 1000.0, 2)
    assert newest["method"] == "Entre contas BankAO" and newest["name"]

    # o histórico é só do próprio utilizador: um terceiro não vê nada
    hc, _ = _user(0)
    assert client.get("/api/contacts/history", headers=hc, params={"key": key}).json()["total"] == 0
    assert client.get("/api/contacts/history", headers=ha, params={"key": "x:1"}).status_code == 422
