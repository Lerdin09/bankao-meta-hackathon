"""Testes de GET /api/accounts/analytics (saldos, dono, agrupamento, merchants, flow, projeção)."""
import datetime
import uuid

import asyncio

import httpx
import pytest

from backend.core.security import create_access_token
from backend.database import get_connection, init_db
from backend.main import app

TODAY = datetime.date.today()


def _d(days_ago):
    return (TODAY - datetime.timedelta(days=days_ago)).isoformat()


class _Client:
    """Transporte ASGI direto (sem sockets, ao contrário do TestClient)."""

    def get(self, url, params=None, headers=None):
        async def _do():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
                return await c.get(url, params=params, headers=headers)

        return asyncio.run(_do())


@pytest.fixture(scope="module")
def client():
    init_db()
    return _Client()


def _user(conn):
    uid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'Analytics', ?, 'hash')",
        (uid, f"an_{uid[:8]}@test.com"),
    )
    return uid


def _account(conn, uid, currency="AOA"):
    aid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, ?)",
        (aid, uid, f"ACC{aid[:8]}", f"IBAN{aid[:8]}", currency),
    )
    return aid


def _entry(conn, aid, amount, tx_type, days_ago, status="completed", description="mov"):
    tx = str(uuid.uuid4())
    conn.execute("INSERT INTO transactions (id, type, status, description) VALUES (?, ?, ?, ?)",
                 (tx, tx_type, status, description))
    conn.execute(
        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at) VALUES (?, ?, ?, 'AOA', ?)",
        (tx, aid, amount, f"{_d(days_ago)} 12:00:00"),
    )
    return tx


def _auth(uid):
    return {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}


def _seed_basic():
    """Saldo: +1000.00 (-10d), -300.00 interna (-5d), -100.00 IBAN (-1d), +50.00 (hoje) = 650.00."""
    with get_connection() as conn:
        uid = _user(conn)
        aid = _account(conn, uid)
        _entry(conn, aid, 100000, "deposit", 10)
        _entry(conn, aid, -30000, "transfer_internal", 5)
        tx_iban = _entry(conn, aid, -10000, "transfer_iban", 1)
        _entry(conn, aid, 5000, "deposit", 0)
        conn.execute(
            """INSERT INTO transfers (id, transaction_id, from_account_id, beneficiary_name,
               source_amount_minor, source_currency, dest_amount_minor, dest_currency, status, created_at)
               VALUES (?, ?, ?, 'Loja X', 10000, 'AOA', 10000, 'AOA', 'completed', ?)""",
            (str(uuid.uuid4()), tx_iban, aid, f"{_d(1)} 12:00:00"),
        )
        conn.execute(
            "INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date) VALUES (?, ?, 'Mercado Y', 'Outros', 5000, 'AOA', ?)",
            (str(uuid.uuid4()), uid, _d(2)),
        )
    return uid, aid


def test_summary_balance_series_and_auth_required(client):
    uid, aid = _seed_basic()
    assert client.get("/api/accounts/analytics").status_code == 401
    r = client.get("/api/accounts/analytics", params={"account_id": aid, "range_days": 30}, headers=_auth(uid))
    assert r.status_code == 200, r.text
    b = r.json()
    s = b["summary"]
    assert s["current_balance"] == 650.00 and s["current_balance_minor"] == 65000
    assert s["initial_balance"] == 0.00 and s["initial_balance_minor"] == 0
    assert s["total_in"] == 1050.00 and s["total_out"] == 400.00 and s["net"] == 650.00
    assert s["max_balance"] == 1000.00 and s["min_balance"] == 0.00
    assert b["balance_series"][-1]["balance"] == 650.00
    assert b["balance_series"][0]["date"] == _d(29)
    assert len(b["operations"]) == 4


def test_owner_filter_403_and_404(client):
    uid, aid = _seed_basic()
    with get_connection() as conn:
        other = _user(conn)
    assert client.get("/api/accounts/analytics", params={"account_id": aid}, headers=_auth(other)).status_code == 403
    assert client.get("/api/accounts/analytics", params={"account_id": "nao-existe"}, headers=_auth(uid)).status_code == 404


def test_grouping_merchants_flow_per_account(client):
    uid, aid = _seed_basic()
    r = client.get("/api/accounts/analytics",
                   params={"account_id": aid, "range_days": 30, "granularity": "month"},
                   headers=_auth(uid))
    b = r.json()
    assert b["in_out_series"] and all("period" in p and "in" in p and "out" in p for p in b["in_out_series"])
    assert b["by_week"] and b["by_month"] and b["by_year"]
    names = [m["name"] for m in b["merchants"]]
    assert names[0] == "Loja X" and "Mercado Y" in names
    assert b["merchants"][0]["total"] == 100.00 and b["merchants"][0]["count"] == 1
    links = {(l["source"], l["target"]): l["value"] for l in b["flow"]["links"]}
    assert links[("depositos", "conta")] == 1050.00
    assert links[("conta", "iban")] == 100.00
    assert links[("conta", "transferencias_internas")] == 300.00
    assert links[("conta", "despesas")] == 50.00
    pa = b["per_account"][0]
    assert pa["by_kind"]["levantamentos"] == 300.00
    assert pa["by_kind"]["compras"] == 150.00  # 100 IBAN + 50 despesa


def test_estornos_pendentes_and_projection_estimate(client):
    with get_connection() as conn:
        uid = _user(conn)
        aid = _account(conn, uid)
        _entry(conn, aid, 10000, "deposit", 100)       # fora do lookback de 90d, dentro do saldo
        _entry(conn, aid, -9000, "transfer_iban", 80)  # despesa no lookback
        _entry(conn, aid, 2000, "savings_refund", 2)   # estorno (crédito não-depósito)
        txp = str(uuid.uuid4())
        conn.execute("INSERT INTO transactions (id, type, status) VALUES (?, 'deposit', 'pending')", (txp,))
        conn.execute(
            "INSERT INTO deposits (id, transaction_id, account_id, method, amount_minor, currency, status) VALUES (?, ?, ?, 'referencia', 7000, 'AOA', 'pending')",
            (str(uuid.uuid4()), txp, aid),
        )
        conn.execute(
            "INSERT INTO savings_goals (id, user_id, name, target_minor, monthly_minor) VALUES (?, ?, 'Meta', 100000, 3000)",
            (str(uuid.uuid4()), uid),
        )
    r = client.get("/api/accounts/analytics",
                   params={"account_id": aid, "range_days": 90, "projection_days": 30},
                   headers=_auth(uid))
    assert r.status_code == 200, r.text
    b = r.json()
    pa = b["per_account"][0]
    assert pa["by_kind"]["estornos"] == 20.00
    assert pa["by_kind"]["pendentes"] == 70.00
    proj = b["projection"]
    assert proj["is_estimate"] is True
    assert proj["assumptions"]["scheduled_savings_monthly"] == 30.00
    assert len(proj["points"]) == 30 and all(p["projected"] for p in proj["points"])
    # saldo atual 30.00, despesa média mensal 30.00 -> cruza <10% e gera alerta
    assert proj["low_balance_alerts"]


def test_empty_account_and_validation(client):
    with get_connection() as conn:
        uid = _user(conn)
        aid = _account(conn, uid)
    r = client.get("/api/accounts/analytics", params={"account_id": aid}, headers=_auth(uid))
    b = r.json()
    assert r.status_code == 200
    assert b["summary"]["current_balance"] == 0.00 and b["summary"]["total_in"] == 0.00
    assert b["balance_series"] == [] and b["operations"] == []
    assert b["flow"] == {"nodes": [], "links": []}
    assert client.get("/api/accounts/analytics", params={"range_days": 45}, headers=_auth(uid)).status_code == 422
    assert client.get("/api/accounts/analytics", params={"granularity": "year"}, headers=_auth(uid)).status_code == 422
