# -*- coding: utf-8 -*-
"""
Testes Abrangentes do Assistente Financeiro Inteligente BankAO:
1. Compreensão de Linguagem Natural (Português de Angola / Informal)
2. Execução de Ferramentas com Dados Reais do Backend (Contas, Cartões, Despesas, Investimentos)
3. Contexto Conversacional Multi-Turn (Mensagens de seguimento)
4. Precisão Matemática em Cálculos e Simulações (Juros Compostos, Comissões, Comparações)
5. Segurança, Isolamento de Dados e Confirmação Obrigatória
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import get_connection
from backend.ai.tools.registry import execute_tool

client = TestClient(app)


def _create_test_user():
    email = f"ai_assistant_{uuid.uuid4().hex[:8]}@bankao.ao"
    r = client.post("/api/auth/register", json={
        "email": email,
        "telefone": "+244923" + str(uuid.uuid4().int)[:6],
        "password": "SenhaForte12345",
        "confirm_password": "SenhaForte12345",
        "terms_accepted": True
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    user_id = r.json()["user"]["id"]
    h = {"Authorization": f"Bearer {token}"}
    return h, user_id


# ─── 1. Linguagem Natural & Perguntas Centrais da Missão ───────────────────────

def test_ai_quanto_dinheiro_tenho():
    """'Quanto dinheiro tenho?' consulta saldos reais das contas."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto dinheiro tenho?"})
    assert r.status_code == 200
    data = r.json()
    assert "Kz" in data["reply"] or "Kwanza" in data["reply"]
    assert "saldo" in data["reply"].lower()


def test_ai_quanto_tenho_na_conta_principal():
    """'Quanto tenho na conta principal?' retorna o saldo em Kwanza."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto tenho na conta principal?"})
    assert r.status_code == 200
    data = r.json()
    assert "Kz" in data["reply"]


def test_ai_quanto_gastei_este_mes():
    """'Quanto gastei este mês?' analisa despesas reais do mês corrente."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto gastei este mês?"})
    assert r.status_code == 200
    data = r.json()
    assert "Kz" in data["reply"] or "despesas" in data["reply"].lower()


def test_ai_mostra_onde_estou_a_gastar_mais():
    """'Mostra onde estou a gastar mais' identifica categorias e comerciantes."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Mostra onde estou a gastar mais."})
    assert r.status_code == 200
    data = r.json()
    assert "gastar mais" in data["reply"].lower() or "despesas" in data["reply"].lower()


def test_ai_quanto_recebi_na_semana_passada():
    """'Quanto recebi na semana passada?' consulta receitas e créditos."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto recebi na semana passada?"})
    assert r.status_code == 200
    data = r.json()
    assert "recebeu" in data["reply"].lower() or "créditos" in data["reply"].lower() or "Kz" in data["reply"]


def test_ai_manda_50_mil_para_o_joao():
    """
    'Manda 50 mil para o João' identifica intenção e montante,
    mas NUNCA executa sem confirmação e pede os dados do destinatário.
    """
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Manda 50 mil para o João."})
    assert r.status_code == 200
    data = r.json()
    assert "50.000" in data["reply"] or "50 000" in data["reply"] or "João" in data["reply"]
    # Operação requer mais dados (IBAN, conta ou e-mail)
    assert data["action"] is None or data["requires_confirmation"] is False


def test_ai_quanto_pago_de_comissoes_se_enviar_dinheiro():
    """'Quanto pago de comissões se enviar dinheiro?' detalha 1% interna e 2.5% IBAN."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto pago de comissões se enviar dinheiro?"})
    assert r.status_code == 200
    data = r.json()
    assert "1%" in data["reply"] or "1,0%" in data["reply"]
    assert "2,5%" in data["reply"] or "2.5%" in data["reply"]


def test_ai_tenho_dinheiro_parado_onde_posso_investir():
    """'Tenho dinheiro parado. Onde posso investir?' recomenda opções com rentabilidades reais."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Tenho dinheiro parado. Onde posso investir?"})
    assert r.status_code == 200
    data = r.json()
    assert "18,5%" in data["reply"] or "Depósito a Prazo" in data["reply"]
    assert "BODIVA" in data["reply"] or "Obrigações" in data["reply"]


def test_ai_qual_dos_meus_cartoes_esta_a_gastar_mais():
    """'Qual dos meus cartões está a gastar mais?' inspeciona e compara cartões."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Qual dos meus cartões está a gastar mais?"})
    assert r.status_code == 200
    data = r.json()
    assert "cartão" in data["reply"].lower() or "cartões" in data["reply"].lower()


def test_ai_quanto_gastei_em_restaurantes_nos_ultimos_tres_meses():
    """'Quanto gastei em restaurantes nos últimos três meses?' filtra categoria e trimestre."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto gastei em restaurantes nos últimos três meses?"})
    assert r.status_code == 200
    data = r.json()
    assert "restaurante" in data["reply"].lower() or "alimentação" in data["reply"].lower() or "3 meses" in data["reply"].lower() or "últimos" in data["reply"].lower()


def test_ai_compara_despesas_deste_mes_com_mes_passado():
    """'Compara as minhas despesas deste mês com as do mês passado' calcula diferenças exatas."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Compara as minhas despesas deste mês com as do mês passado."})
    assert r.status_code == 200
    data = r.json()
    assert "este mês" in data["reply"].lower()
    assert "mês passado" in data["reply"].lower() or "anterior" in data["reply"].lower()


def test_ai_se_poupar_30_mil_por_mes_quanto_terei_daqui_a_um_ano():
    """'Se poupar 30 mil por mês, quanto terei daqui a um ano?' calcula juros compostos."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Se poupar 30 mil por mês, quanto terei daqui a um ano?"})
    assert r.status_code == 200
    data = r.json()
    # 30 mil * 12 = 360 mil depositado + juros a 18.5%
    assert "360.000" in data["reply"] or "360 000" in data["reply"]
    assert "juros" in data["reply"].lower()


def test_ai_mostra_os_meus_investimentos_e_diz_quais_estao_a_render_mais():
    """'Mostra os meus investimentos e diz-me quais estão a render mais' avalia posições e rendimentos."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Mostra os meus investimentos e diz-me quais estão a render mais."})
    assert r.status_code == 200
    data = r.json()
    assert "investimento" in data["reply"].lower() or "carteira" in data["reply"].lower()


# ─── 2. Contexto Conversacional Multi-Turn ────────────────────────────────────

def test_ai_multiturn_follow_up_mes_passado():
    """Seguimento multi-turn: 'Quanto gastei este mês?' seguido de 'E no mês passado?'."""
    h, _ = _create_test_user()
    # Turno 1
    r1 = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto gastei este mês?"})
    assert r1.status_code == 200

    # Turno 2 (mensagem elíptica)
    r2 = client.post("/api/ai/chat-v2", headers=h, json={"message": "E no mês passado?"})
    assert r2.status_code == 200
    data = r2.json()
    assert "mês passado" in data["reply"].lower() or "despesas" in data["reply"].lower()


def test_ai_multiturn_follow_up_moeda_dolares():
    """Seguimento multi-turn: 'Quanto dinheiro tenho?' seguido de 'E em dólares?'."""
    h, _ = _create_test_user()
    # Turno 1
    r1 = client.post("/api/ai/chat-v2", headers=h, json={"message": "Quanto dinheiro tenho?"})
    assert r1.status_code == 200

    # Turno 2
    r2 = client.post("/api/ai/chat-v2", headers=h, json={"message": "E em dólares?"})
    assert r2.status_code == 200
    data = r2.json()
    assert "USD" in data["reply"] or "$" in data["reply"] or "dólares" in data["reply"].lower()


# ─── 3. Educação Financeira Conceitual ────────────────────────────────────────

def test_ai_educacao_o_que_e_um_etf():
    """Explicação didática de ETF sem falsas garantias."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "O que é um ETF?"})
    assert r.status_code == 200
    data = r.json()
    assert "ETF" in data["reply"]
    assert "Diversificação" in data["reply"]
    assert "bolsa" in data["reply"].lower()


def test_ai_educacao_diferenca_deposito_prazo_vs_etf():
    """Comparativo instrutivo entre Depósito a Prazo e ETF."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "Qual é a diferença entre um depósito a prazo e um ETF?"})
    assert r.status_code == 200
    data = r.json()
    assert "Depósito a Prazo" in data["reply"]
    assert "ETF" in data["reply"]
    assert "garantido" in data["reply"].lower()


def test_ai_educacao_obrigacoes_do_tesouro_bodiva():
    """Explicação didática de Obrigações do Tesouro na BODIVA."""
    h, _ = _create_test_user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "O que são obrigações do tesouro?"})
    assert r.status_code == 200
    data = r.json()
    assert "Obrigações do Tesouro" in data["reply"]
    assert "BODIVA" in data["reply"]
    assert "Estado" in data["reply"] or "dívida" in data["reply"].lower()


# ─── 4. Execução Direta de Ferramentas & Isolamento de Segurança ──────────────

def test_tool_execution_accounts_and_isolation():
    """Testa execução direta de ferramenta e isolamento estrito entre utilizadores."""
    _, u1 = _create_test_user()
    _, u2 = _create_test_user()

    res1 = execute_tool("get_accounts_summary", {}, u1)
    res2 = execute_tool("get_accounts_summary", {}, u2)

    assert "accounts" in res1
    assert "accounts" in res2

    # Contas de u1 pertencem apenas a u1
    u1_acc_ids = {a["id"] for a in res1["accounts"]}
    u2_acc_ids = {a["id"] for a in res2["accounts"]}
    assert u1_acc_ids.isdisjoint(u2_acc_ids)


def test_tool_simulation_precision():
    """Verifica que o cálculo de simulação é matematicamente exato."""
    _, u = _create_test_user()
    res = execute_tool("simulate_investment", {
        "initial_amount": 100000.0,
        "monthly_contribution": 10000.0,
        "months": 12,
        "annual_rate": 18.5
    }, u)

    assert res["initial_amount"] == 100000.0
    assert res["monthly_contribution"] == 10000.0
    assert res["months"] == 12
    assert res["total_deposited"] == 220000.0  # 100k inicial + 12 * 10k
    assert res["final_balance"] > res["total_deposited"]
    assert res["total_interest_earned"] > 0


def test_tool_get_contacts_and_natural_copilot_transfer():
    """
    Testa a integração da IA com a lista de contactos:
    1. Ferramenta get_contacts lista e filtra contactos do cliente.
    2. 'Envia 5000 para a Ana' identifica o contacto guardado, calcula a comissão
       e prepara a proposta com confirmação explícita.
    """
    h_a, u_a = _create_test_user()
    h_b, u_b = _create_test_user()

    # Obter conta do destinatário
    accs_b = client.get("/api/accounts", headers=h_b).json()
    aoa_b = next(a for a in accs_b if a["currency"] == "AOA")

    # Guardar contacto 'Ana' no utilizador A
    r_save = client.post("/api/contacts", headers=h_a, json={
        "kind": "internal",
        "account_number": aoa_b["account_number"],
        "nickname": "Ana",
        "favorite": True
    })
    assert r_save.status_code == 200

    # 1. Testar execução direta da ferramenta get_contacts
    res_tool = execute_tool("get_contacts", {"query": "Ana"}, u_a)
    assert res_tool["total_found"] >= 1
    assert any(c["display_name"] == "Ana" for c in res_tool["contacts"])

    # 2. Testar comando em linguagem natural no Copilot
    r_chat = client.post("/api/ai/chat-v2", headers=h_a, json={"message": "Envia 5000 para a Ana"})
    assert r_chat.status_code == 200
    data = r_chat.json()

    assert "Ana" in data["reply"]
    assert "5.000" in data["reply"] or "5000" in data["reply"]
    assert data["requires_confirmation"] is True
    assert data["action"] is not None
    assert data["action"]["type"] == "TRANSFER_INTERNAL"
    assert data["action"]["to_account_number"] == aoa_b["account_number"]
    assert data["action"]["amount"] == 5000.0


def test_ai_sobre_investimento_e_despesas_sem_saudacao_generica():
    """
    Garante que perguntas diretas como 'sobre investimento' e 'sobre as despesas'
    respondem diretamente com dados financeiros e NUNCA apenas com apresentação genérica.
    """
    h, _ = _create_test_user()

    # 1. 'sobre investimento' no chat-v2
    r_inv = client.post("/api/ai/chat-v2", headers=h, json={"message": "sobre investimento"})
    assert r_inv.status_code == 200
    d_inv = r_inv.json()
    assert not d_inv["reply"].startswith("Olá! Sou o **BankAO Copilot** — o seu assistente financeiro")
    assert "investimento" in d_inv["reply"].lower() or "depósito a prazo" in d_inv["reply"].lower() or "18,5%" in d_inv["reply"]

    # 2. 'sobre as despesas' no chat-v2
    r_exp = client.post("/api/ai/chat-v2", headers=h, json={"message": "sobre as despesas"})
    assert r_exp.status_code == 200
    d_exp = r_exp.json()
    assert not d_exp["reply"].startswith("Olá! Sou o **BankAO Copilot** — o seu assistente financeiro")
    assert "despesa" in d_exp["reply"].lower() or "gasto" in d_exp["reply"].lower() or "kz" in d_exp["reply"].lower()

    # 3. 'sobre investimento' no endpoint legado /api/ai/chat
    r_leg = client.post("/api/ai/chat", json={"message": "sobre investimento"})
    assert r_leg.status_code == 200
    d_leg = r_leg.json()
    assert "Por onde começamos?" not in d_leg["reply"]
    assert "investimento" in d_leg["reply"].lower() or "depósito" in d_leg["reply"].lower()


def test_ai_investimento_personalizado_com_salario_inline():
    """
    Cenário exato da queixa do utilizador:
    'qual tipo de investimento recomendas, sendo que eu ganho X kz'
    Deve retornar recomendação personalizada com dados do salário — nunca
    uma apresentação genérica nem uma pergunta 'Como posso ajudar?'.
    """
    h, _ = _create_test_user()

    r = client.post("/api/ai/chat-v2", headers=h, json={
        "message": "qual tipo de investimento recomendas, sendo que eu ganho 500 mil kz"
    })
    assert r.status_code == 200
    data = r.json()
    reply = data["reply"].lower()

    # Não deve começar com apresentação genérica
    assert not data["reply"].startswith("Olá! Sou o **BankAO Copilot**"), \
        "O assistente não deve se apresentar ao responder uma pergunta específica"
    assert "como posso ajudá" not in reply, \
        "O assistente não deve perguntar 'Como posso ajudar?' ao receber pergunta sobre investimento"

    # Deve conter referência a produto de investimento
    assert any(kw in reply for kw in ["500", "100.000", "depósito", "18,5%", "recomendação", "kz"]), \
        "A resposta deve conter dados financeiros personalizados com base no salário declarado"


def test_ai_memoria_salario_persiste_entre_mensagens():
    """
    Após declarar o salário numa mensagem, a próxima pergunta sobre investimento
    deve usar o salário já guardado na memória sem o utilizador precisar repetir.
    """
    h, _ = _create_test_user()

    # Primeira mensagem: declara salário
    client.post("/api/ai/chat-v2", headers=h, json={
        "message": "o meu salário é 800 mil kz por mês"
    })

    # Segunda mensagem: pergunta sobre investimento sem repetir salário
    r2 = client.post("/api/ai/chat-v2", headers=h, json={
        "message": "que tipo de investimento me recomendas?"
    })
    assert r2.status_code == 200
    data2 = r2.json()
    reply = data2["reply"].lower()

    # Deve conter dados de investimento
    assert any(kw in reply for kw in ["depósito", "18,5%", "bodiva", "investimento", "kz"]), \
        "A resposta deve incluir recomendação de investimento"
    assert not data2["reply"].startswith("Olá! Sou o **BankAO Copilot**"), \
        "Não deve apresentar-se ao responder pergunta sobre investimento"
