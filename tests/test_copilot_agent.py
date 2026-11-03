# -*- coding: utf-8 -*-
"""
Copilot (agente): o modelo decide, as ferramentas preparam, o utilizador conclui.
Usa um modelo simulado (sem rede) que pede ferramentas e depois responde.
"""
import json
from types import SimpleNamespace

import pytest

from backend.ai import agent as agent_mod
from backend.ai.tools import actions


# ---------------------------------------------------------------------------
# Modelo simulado
# ---------------------------------------------------------------------------
def _tool_call(call_id, name, args):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def _reply(content=None, calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls))])


class FakeClient:
    """Devolve respostas pré-definidas, na ordem; guarda os pedidos recebidos."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def _sem_base_de_dados(monkeypatch):
    monkeypatch.setattr(agent_mod, "_customer_brief", lambda uid: {"name": "Teste", "notes": {}})
    monkeypatch.setattr(actions, "get_user_accounts", lambda uid: [
        {"id": "a1", "currency": "AOA", "account_number": "004000000001", "balance_decimal": 100000.0}])
    agent_mod.update_user_session("u-test", {"last_action": None, "pending_operation": None})


def run(client, msg, history=None):
    return agent_mod.run_agent(client, "u-test", msg, history)


# ---------------------------------------------------------------------------
# Ferramentas de ação
# ---------------------------------------------------------------------------
def test_meta_carro_e_meta_nao_despesa_e_valor_nao_vira_ano():
    r = actions.tool_prepare_savings_goal("u", name="Carro", icon_key="car", target_amount=50000,
                                          deadline="2027-08", auto_debit=False)
    assert r["ok"] and r["executed"] is False
    a = r["action"]
    assert a["type"] == "CREATE_SAVINGS_GOAL" and a["target"] == 50000.0
    assert a["deadline"] == "2027-08" and a["icon_key"] == "car"


def test_meta_sem_dia_pergunta_o_dia_em_vez_de_inventar():
    r = actions.tool_prepare_savings_goal("u", name="Casa", target_amount=900000, months=24)
    assert not r["ok"] and r["missing"] == ["debit_day"]


def test_meta_sem_prazo_pede_prazo():
    r = actions.tool_prepare_savings_goal("u", name="Viagem", target_amount=300000, auto_debit=False)
    assert not r["ok"] and "prazo" in r["error"].lower()


def test_despesa_valida_categoria_e_data_futura():
    ok = actions.tool_prepare_expense("u", name="Táxi", amount=2500, category="Transporte")
    assert ok["ok"] and ok["action"]["amount"] == 2500.0 and ok["action"]["category"] == "Transporte"
    outra = actions.tool_prepare_expense("u", name="X", amount=10, category="Inventada")
    assert outra["action"]["category"] == "Outros"
    futura = actions.tool_prepare_expense("u", name="X", amount=10, category="Outros", expense_date="2999-01-01")
    assert not futura["ok"]


def test_transferencia_por_conta_nunca_vai_para_o_formulario_do_iban():
    r = actions.tool_prepare_transfer("u", method="account", destination="0040 1234 5678", amount=5000)
    assert r["ok"] and r["action"]["type"] == "TRANSFER_INTERNAL"
    assert r["action"]["to_account_number"] == "004012345678" and "to_iban" not in r["action"]
    assert r["has_sufficient_funds"] is True
    # método errado para o destino → erro claro, nunca um formulário trocado
    assert not actions.tool_prepare_transfer("u", method="iban", destination="004012345678", amount=5000)["ok"]


def test_transferencia_por_iban_e_deteta_saldo_insuficiente():
    iban = "AO06004000010000000000010"  # forma de IBAN angolano (pode não passar Mod 97)
    r = actions.tool_prepare_transfer("u", method="iban", destination=iban, amount=500000, beneficiary_name="Ana")
    assert r["ok"] and r["action"]["type"] == "TRANSFER_IBAN" and r["action"]["to_iban"] == iban
    assert r["has_sufficient_funds"] is False and "iban_valid" in r
    assert not actions.tool_prepare_transfer("u", method="account", destination=iban, amount=100)["ok"]


def test_deposito_valida_telemovel():
    assert actions.tool_prepare_deposit("u", "923 456 789", 10000)["ok"]
    assert not actions.tool_prepare_deposit("u", "12345", 10000)["ok"]


# ---------------------------------------------------------------------------
# Agente
# ---------------------------------------------------------------------------
def test_agente_prepara_meta_e_devolve_acao_sem_afirmar_que_criou():
    client = FakeClient(
        _reply(calls=[_tool_call("1", "prepare_savings_goal", {
            "name": "Carro", "icon_key": "car", "target_amount": 50000, "deadline": "2027-08", "auto_debit": False})]),
        _reply("Preparei a meta Carro de 50.000 Kz até agosto de 2027. Está pronta para rever no cartão."),
    )
    res = run(client, "quero poupar 50 mil para um carro até agosto de 2027, sem débito automático")
    assert res["action"]["type"] == "CREATE_SAVINGS_GOAL" and res["action"]["target"] == 50000.0
    assert res["requires_confirmation"] is True and res["pending"] is None
    assert res["tools_used"] == ["prepare_savings_goal"]


def test_agente_corrige_afirmacao_de_conclusao():
    client = FakeClient(
        _reply(calls=[_tool_call("1", "prepare_transfer", {"method": "account", "destination": "004012345678", "amount": 5000})]),
        _reply("Transferi 5.000 Kz para a conta."),
    )
    res = run(client, "transfere 5000 para a conta 004012345678")
    assert res["action"]["type"] == "TRANSFER_INTERNAL"
    assert "não foi concluído" in res["reply"]


def test_agente_sem_ferramenta_responde_direto_sem_saudacao_nem_extras():
    client = FakeClient(_reply("Em kwanzas, 50 mil são 50.000 Kz."))
    res = run(client, "quanto são 50 mil em kz?")
    assert res["reply"] == "Em kwanzas, 50 mil são 50.000 Kz." and res["action"] is None and res["tools_used"] == []


def test_ferramenta_falhada_nao_deixa_cartao_antigo():
    client = FakeClient(
        _reply(calls=[_tool_call("1", "prepare_transfer", {"method": "iban", "destination": "123", "amount": 10})]),
        _reply("Esse destino não é um IBAN. Pode dar-me o IBAN completo?"),
    )
    res = run(client, "envia 10 para 123 por iban")
    assert res["action"] is None and res["requires_confirmation"] is False


def test_ultima_acao_e_historico_chegam_ao_modelo_para_correcoes():
    first = FakeClient(
        _reply(calls=[_tool_call("1", "prepare_expense", {"name": "Almoço", "amount": 4000, "category": "Alimentação"})]),
        _reply("Despesa de 4.000 Kz preparada."),
    )
    run(first, "gastei 4000 no almoço")
    second = FakeClient(_reply("Ok."))
    run(second, "afinal foram 5000", history=[{"role": "user", "content": "gastei 4000 no almoço"},
                                              {"role": "assistant", "content": "Despesa de 4.000 Kz preparada."}])
    sent = second.requests[0]["messages"]
    assert "Última ação" in sent[0]["content"] and "Almoço" in sent[0]["content"]
    assert [m["role"] for m in sent[1:]] == ["user", "assistant", "user"]


def test_modelo_calado_usa_o_resumo_da_ferramenta_e_sem_nada_devolve_none():
    client = FakeClient(
        _reply(calls=[_tool_call("1", "prepare_deposit", {"phone_number": "923456789", "amount": 10000})]),
        _reply(""),
    )
    res = run(client, "deposita 10 mil do 923456789")
    assert res["action"]["type"] == "DEPOSIT_EXPRESS" and "não foi enviado" in res["reply"]
    assert run(FakeClient(_reply("")), "olá") is None


def test_prompt_inclui_data_de_hoje_e_proibe_conversa_nao_pedida():
    client = FakeClient(_reply("Ok."))
    run(client, "olá")
    system = client.requests[0]["messages"][0]["content"]
    assert "Hoje:" in system and "Nunca metes conversa que não foi pedida" in system
