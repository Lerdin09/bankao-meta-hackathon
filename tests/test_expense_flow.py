# -*- coding: utf-8 -*-
"""
Despesas no Copilot: registo direto («comprei um telefone de 22 mil») e remoção detalhada
(«remove a despesa do telefone que comprei ontem a 22 mil»). Base de dados temporária, sem rede.
"""
import uuid
from datetime import date, timedelta

import pytest

from backend.ai import expense_flow as ef
from backend.ai.intents import analyze_message
from backend.ai.orchestrator import CopilotOrchestrator
from backend.database import connection, get_connection, init_db

HOJE = date.today()
ONTEM = HOJE - timedelta(days=1)


@pytest.fixture()
def uid(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, "DB_PATH", str(tmp_path / "t.db"))
    init_db()
    u = str(uuid.uuid4())
    with get_connection() as c:
        c.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'T', ?, 'x')", (u, f"{u}@t.ao"))
        c.commit()
    return u


def add(uid, name, amount, day, cat="Outros", origin="manual", goal_id=None):
    with get_connection() as c:
        c.execute("INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, goal_id) "
                  "VALUES (?, ?, ?, ?, ?, 'AOA', ?, ?, ?)",
                  (str(uuid.uuid4()), uid, name, cat, int(round(amount * 100)), day.isoformat(), origin, goal_id))
        c.commit()


def rows(uid):
    with get_connection() as c:
        return [dict(r) for r in c.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY created_at, rowid", (uid,))]


def chat(uid, msg, pending=None):
    return CopilotOrchestrator.process_message(uid, msg, [], pending)


# ---------------------------------------------------------------------------
# Registo direto
# ---------------------------------------------------------------------------
def test_comprei_um_telefone_regista_logo_em_eletronicos(uid):
    r = chat(uid, "comprei um telefone de 22mil")
    a = r["action"]
    assert a["type"] == "EXPENSE_REGISTERED" and r["requires_confirmation"] is False and r["pending"] is None
    assert "Registei" in r["reply"] and "ainda não foi registada" not in r["reply"].lower()
    (e,) = rows(uid)
    assert (e["name"], e["amount_minor"], e["category"], e["expense_date"], e["origin"]) == \
           ("Telefone", 2_200_000, "Eletrónicos", HOJE.isoformat(), "ai")


def test_categoria_dita_e_nome_limpo(uid):
    chat(uid, "comprei um telefone a 22 mil em eletronicos ontem")
    (e,) = rows(uid)
    assert (e["name"], e["category"], e["expense_date"]) == ("Telefone", "Eletrónicos", ONTEM.isoformat())


def test_servicos_de_telecom_continuam_em_telecomunicacoes():
    assert analyze_message("paguei 8500 na Unitel")["action"]["category"] == "Telecomunicações"
    assert analyze_message("carreguei saldo de 2000 no telefone, gastei 2000")["action"]["category"] == "Telecomunicações"
    assert analyze_message("comprei um portátil de 350 mil")["action"]["category"] == "Eletrónicos"


def test_sem_valor_pergunta_o_valor_e_depois_regista(uid):
    r = chat(uid, "comprei um telefone")
    assert r["action"] is None and r["pending"] and rows(uid) == []
    r = chat(uid, "22 mil", r["pending"])
    assert r["action"]["type"] == "EXPENSE_REGISTERED"
    (e,) = rows(uid)
    assert e["name"] == "Telefone" and e["amount_minor"] == 2_200_000


def test_pedido_repetido_em_menos_de_um_minuto_nao_duplica(uid):
    chat(uid, "gastei 5000 de táxi")
    r = chat(uid, "gastei 5000 de táxi")
    assert len(rows(uid)) == 1 and "já estava registada" in r["reply"]


def test_ferramenta_do_modelo_tambem_regista_logo(uid):
    from backend.ai.tools.actions import tool_prepare_expense
    res = tool_prepare_expense(uid, name="Telefone", amount=22000, category="Eletrónicos")
    out = ef.apply_direct_registration(uid, {"reply": "x", "action": res["action"], "pending": None})
    assert out["action"]["type"] == "EXPENSE_REGISTERED" and rows(uid)[0]["category"] == "Eletrónicos"


# ---------------------------------------------------------------------------
# Remoção
# ---------------------------------------------------------------------------
def test_remove_a_despesa_do_telefone_de_ontem_a_22mil(uid):
    add(uid, "Telefone", 22000, ONTEM, "Eletrónicos")
    add(uid, "Táxi", 5000, ONTEM, "Transporte")
    r = chat(uid, "remova a despesa do telefone que comprei ontem a 22mil")
    assert r["action"]["type"] == "EXPENSE_DELETED" and "Removi" in r["reply"]
    assert [e["name"] for e in rows(uid)] == ["Táxi"]


def test_sem_detalhe_suficiente_nao_apaga_e_pede_mais(uid):
    add(uid, "Telefone", 22000, ONTEM)
    r = chat(uid, "remove a despesa")
    assert r["action"] is None and r["pending"]["type"] == "DELETE_EXPENSE" and len(rows(uid)) == 1
    r = chat(uid, "a do telefone", r["pending"])                    # só o nome: ainda é pouco
    assert r["action"] is None and len(rows(uid)) == 1 and "Telefone" in r["reply"]
    r = chat(uid, "de 22 mil", r["pending"])                         # nome + valor: chega
    assert r["action"]["type"] == "EXPENSE_DELETED" and rows(uid) == []


def test_nao_encontra_nao_apaga(uid):
    add(uid, "Telefone", 22000, ONTEM)
    r = chat(uid, "remove a despesa do telefone de 30 mil de ontem")
    assert r["action"] is None and "Não encontrei" in r["reply"] and len(rows(uid)) == 1


def test_dia_errado_nao_apaga(uid):
    add(uid, "Telefone", 22000, HOJE)
    r = chat(uid, "remova a despesa do telefone que comprei ontem a 22mil")
    assert r["action"] is None and len(rows(uid)) == 1


def test_duas_candidatas_diferentes_pergunta_qual(uid):
    add(uid, "Telefone Samsung", 22000, ONTEM)
    add(uid, "Telefone Xiaomi", 22000, ONTEM)
    r = chat(uid, "apaga a despesa do telefone de 22 mil de ontem")
    assert r["action"] is None and len(rows(uid)) == 2 and "mais do que uma" in r["reply"]
    r = chat(uid, "o xiaomi", r["pending"])
    assert r["action"]["type"] == "EXPENSE_DELETED"
    assert [e["name"] for e in rows(uid)] == ["Telefone Samsung"]


def test_duas_iguais_apaga_so_uma(uid):
    add(uid, "Telefone", 22000, ONTEM)
    add(uid, "Telefone", 22000, ONTEM)
    r = chat(uid, "remove a despesa do telefone de 22 mil de ontem")
    assert r["action"]["type"] == "EXPENSE_DELETED" and len(rows(uid)) == 1 and "só a mais recente" in r["reply"]


def test_data_por_extenso(uid):
    d = HOJE.replace(day=1)
    add(uid, "Renda", 150000, d, "Habitação")
    r = chat(uid, "elimina a despesa da renda de 150 mil do dia 1")
    if HOJE.day == 1 or d <= HOJE:
        assert r["action"]["type"] == "EXPENSE_DELETED" and rows(uid) == []


def test_despesas_de_poupanca_e_transferencia_nao_se_removem(uid):
    add(uid, "Depósito Carro", 10000, ONTEM, "Poupança", origin="savings")
    r = chat(uid, "remove a despesa do depósito carro de 10 mil de ontem")
    assert r["action"] is None and "não a posso remover" in r["reply"] and len(rows(uid)) == 1


def test_so_apaga_as_despesas_do_proprio_utilizador(uid):
    outro = str(uuid.uuid4())
    with get_connection() as c:
        c.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'O', ?, 'x')", (outro, f"{outro}@t.ao"))
        c.commit()
    add(outro, "Telefone", 22000, ONTEM)
    r = chat(uid, "remove a despesa do telefone de 22 mil de ontem")
    assert r["action"] is None and len(rows(outro)) == 1


def test_perguntas_e_outros_pedidos_nao_apagam_nada(uid):
    add(uid, "Telefone", 22000, ONTEM)
    assert ef.handle_expense_delete(uid, "como removo uma despesa?") is None
    assert ef.handle_expense_delete(uid, "posso apagar uma despesa do telefone?") is None
    assert ef.handle_expense_delete(uid, "quanto gastei em telefone ontem?") is None
    assert ef.handle_expense_delete(uid, "cancela o meu cartão") is None
    assert len(rows(uid)) == 1


def test_pergunta_a_meio_abandona_a_remocao(uid):
    add(uid, "Telefone", 22000, ONTEM)
    r = ef.handle_expense_delete(uid, "remove a despesa")
    assert ef.handle_expense_delete(uid, "qual é o meu saldo?", r["pending"]) is None
    r = ef.handle_expense_delete(uid, "esquece", r["pending"])
    assert r["pending"] is None and len(rows(uid)) == 1


def test_levantar_dinheiro_ou_pedido_novo_nao_e_remocao(uid):
    add(uid, "Telefone", 22000, ONTEM)
    assert ef.handle_expense_delete(uid, "quero retirar 20 mil para compras") is None
    r = ef.handle_expense_delete(uid, "remove a despesa")
    assert ef.handle_expense_delete(uid, "transfere 5000 kz para a conta 004012345678", r["pending"]) is None
    assert ef.handle_expense_delete(uid, "comprei um telefone de 22 mil", r["pending"]) is None
    assert len(rows(uid)) == 1
