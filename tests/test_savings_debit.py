# -*- coding: utf-8 -*-
"""Poupança: o depósito sai da conta, fica em Despesas e o débito automático corre no dia escolhido."""
import datetime
import uuid

import pytest
from fastapi import HTTPException

from backend.api.routes import savings as sv
from backend.database import connection, get_connection, init_db
from backend.schemas import GoalDepositIn, GoalIn
from backend.services.ledger import get_account_balance
from backend.services.savings import clamp_day, next_occurrence, run_auto_savings


@pytest.fixture()
def user(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "t.db"))
    init_db()
    uid, acc = str(uuid.uuid4()), str(uuid.uuid4())
    with get_connection() as c:
        c.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'T', ?, 'x')", (uid, f"{uid}@t.ao"))
        c.execute("INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'AOA')",
                  (acc, uid, uid[:12], "AO" + uid[:20]))
        tx = str(uuid.uuid4())
        c.execute("INSERT INTO transactions (id, type, status) VALUES (?, 'deposit', 'completed')", (tx,))
        c.execute("INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, 10000000, 'AOA')", (tx, acc))
        c.commit()
    return {"id": uid, "acc": acc}


def bal(u):
    return get_account_balance(u["acc"]) / 100


def expenses(u):
    with get_connection() as c:
        return c.execute("SELECT * FROM expenses WHERE user_id = ?", (u["id"],)).fetchall()


def test_deposito_debita_conta_e_regista_despesa(user):
    g = sv.create_goal(GoalIn(name="Casa", target=150000, monthly=10000), user)
    r = sv.deposit_to_goal(g["id"], GoalDepositIn(amount=25000), user)
    assert bal(user) == 75000.0 and r["balance"] == 75000.0
    assert r["goal"]["saved"] == 25000.0
    ex = expenses(user)
    assert len(ex) == 1 and ex[0]["category"] == "Poupança" and ex[0]["amount_minor"] == 2_500_000


def test_saldo_insuficiente_nao_altera_nada(user):
    g = sv.create_goal(GoalIn(name="Casa", target=500000, monthly=10000), user)
    with pytest.raises(HTTPException) as e:
        sv.deposit_to_goal(g["id"], GoalDepositIn(amount=200000), user)
    assert e.value.status_code == 400 and bal(user) == 100000.0 and not expenses(user)


def test_saldo_inicial_tambem_sai_da_conta(user):
    sv.create_goal(GoalIn(name="Carro", target=50000, saved=20000, monthly=5000), user)
    assert bal(user) == 80000.0 and len(expenses(user)) == 1


def test_chave_repetida_nao_debita_duas_vezes(user):
    g = sv.create_goal(GoalIn(name="Casa", target=150000, monthly=10000), user)
    sv.deposit_to_goal(g["id"], GoalDepositIn(amount=1000, idempotency_key="k1"), user)
    with pytest.raises(HTTPException) as e:
        sv.deposit_to_goal(g["id"], GoalDepositIn(amount=1000, idempotency_key="k1"), user)
    assert e.value.status_code == 409 and bal(user) == 99000.0


def test_debito_automatico_no_dia_escolhido_sem_duplicar(user):
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=1)).isoformat()
    day = (today - datetime.timedelta(days=1)).day
    with get_connection() as c:   # meta que devia ter começado ontem
        gid = str(uuid.uuid4())
        c.execute("INSERT INTO savings_goals (id, user_id, name, target_minor, monthly_minor, debit_day, start_date) "
                  "VALUES (?, ?, 'Casa', 15000000, 1000000, ?, ?)", (gid, user["id"], day, start))
        c.commit()
    assert run_auto_savings(user["id"], today) >= 1
    saldo = bal(user)
    assert saldo <= 90000.0
    assert run_auto_savings(user["id"], today) == 0 and bal(user) == saldo     # idempotente
    assert all(e["origin"] == "savings" for e in expenses(user))


def test_auto_nao_corre_antes_da_data_e_espera_por_saldo(user):
    g = sv.create_goal(GoalIn(name="Viagem", target=50000, monthly=10000, debit_day=5,
                              start_date=(datetime.date.today() + datetime.timedelta(days=40)).replace(day=5).isoformat()), user)
    assert run_auto_savings(user["id"]) == 0 and bal(user) == 100000.0
    assert g["debitDay"] == 5


def test_apagar_meta_devolve_o_dinheiro(user):
    g = sv.create_goal(GoalIn(name="Casa", target=150000, monthly=10000), user)
    sv.deposit_to_goal(g["id"], GoalDepositIn(amount=30000), user)
    r = sv.delete_goal(g["id"], user)
    assert r["refunded"] == 30000.0 and bal(user) == 100000.0 and not expenses(user)


def test_dia_31_cai_no_ultimo_dia_do_mes():
    assert clamp_day(2027, 2, 31) == datetime.date(2027, 2, 28)
    assert next_occurrence(5, datetime.date(2026, 12, 5)) == datetime.date(2027, 1, 5)
