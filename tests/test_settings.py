"""Definições: preferências, dados sensíveis só de leitura, segurança, limites e bloqueio."""
import uuid

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.ledger import credit_deposit  # noqa: F401  (apenas para garantir import)

client = TestClient(app)


def _user():
    email = f"set_{uuid.uuid4().hex[:8]}@bankao.ao"
    r = client.post("/api/auth/register", json={"email": email, "telefone": "+244923" + str(uuid.uuid4().int)[:6],
                    "password": "Teste12345", "confirm_password": "Teste12345", "terms_accepted": True})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


def test_read_and_save():
    h, _ = _user()
    d = client.get("/api/settings", headers=h).json()
    assert d["settings"]["theme"] == "dark" and len(d["accounts"]) == 3
    r = client.put("/api/settings", headers=h, json={"values": {"theme": "light", "limit_transfers": 5000, "n_promos": True}})
    assert r.status_code == 200 and r.json()["settings"]["theme"] == "light"
    assert client.get("/api/settings", headers=h).json()["settings"]["limit_transfers"] == 5000


def test_invalid_and_sensitive_rejected():
    h, _ = _user()
    assert client.put("/api/settings", headers=h, json={"values": {"theme": "pink"}}).status_code == 400
    assert client.put("/api/settings", headers=h, json={"values": {"iban": "AO06"}}).status_code == 400
    assert client.put("/api/settings", headers=h, json={"values": {"doc_numero": "1"}}).status_code == 400
    assert client.put("/api/settings", headers=h, json={"values": {"unknown": 1}}).status_code == 400
    for f in ("doc_numero", "iban", "account_number", "nif", "nome"):
        assert client.patch("/api/settings/profile", headers=h, json={f: "x"}).status_code == 422


def test_profile_password_pin():
    h, _ = _user()
    assert client.patch("/api/settings/profile", headers=h, json={"morada": "Luanda"}).json()["profile"]["morada"] == "Luanda"
    assert client.patch("/api/settings/profile", headers=h, json={"telefone": "abc"}).status_code == 400
    assert client.post("/api/settings/password", headers=h, json={"current_password": "x", "new_password": "Nova12345"}).status_code == 400
    assert client.post("/api/settings/password", headers=h, json={"current_password": "Teste12345", "new_password": "Nova12345"}).status_code == 200
    assert client.post("/api/settings/pin", headers=h, json={"pin": "12"}).status_code == 400
    assert client.post("/api/settings/pin", headers=h, json={"pin": "1234"}).status_code == 200
    assert client.post("/api/settings/pin/verify", headers=h, json={"pin": "1234"}).json()["ok"] is True
    assert client.post("/api/settings/pin/verify", headers=h, json={"pin": "0000"}).json()["ok"] is False


def test_sessions_and_revoke():
    h, email = _user()
    r = client.post("/api/auth/login", data=None, json={"email": email, "password": "Teste12345"})
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    s = client.get("/api/settings/sessions", headers=h2).json()
    assert len(s["sessions"]) == 2 and s["current"]
    assert client.post("/api/settings/sessions/revoke-others", headers=h2).status_code == 200
    assert client.get("/api/settings", headers=h).status_code == 401      # a primeira sessão foi terminada
    assert client.get("/api/settings", headers=h2).status_code == 200
    assert len(client.get("/api/settings/login-history", headers=h2).json()["history"]) >= 2


def test_lock_account_blocks_transfers():
    h, _ = _user()
    assert client.post("/api/settings/account-lock", headers=h, json={"lock": True, "password": "errada"}).status_code == 400
    assert client.post("/api/settings/account-lock", headers=h, json={"lock": True, "password": "Teste12345"}).json()["locked"] is True
    assert client.get("/api/settings", headers=h).json()["locked"] is True
    assert client.post("/api/settings/account-lock", headers=h, json={"lock": False, "password": "Teste12345"}).json()["locked"] is False


def test_transfer_limit_enforced():
    h, _ = _user()
    h2, e2 = _user()
    accs = client.get("/api/settings", headers=h).json()["accounts"]
    aoa = next(a for a in accs if a["currency"] == "AOA")
    client.put("/api/settings", headers=h, json={"values": {"limit_transfers": 1000}})
    r = client.post("/api/transfers/internal", headers=h, json={"from_account_id": aoa["id"], "to_email": e2, "amount": 5000, "idempotency_key": "test_limit_idemp"})
    assert r.status_code == 400 and "Limite diário" in r.json()["detail"]


def test_support_request():
    h, _ = _user()
    assert client.post("/api/settings/support", headers=h, json={"kind": "fraude", "message": "Movimento suspeito"}).json()["id"].startswith("REQ-")
    assert client.post("/api/settings/support", headers=h, json={"kind": "xx", "message": "abc def"}).status_code == 400
