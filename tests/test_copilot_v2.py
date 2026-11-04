# -*- coding: utf-8 -*-
"""
Testes abrangentes do Copilot v2:
- Perguntas simples com respostas simples e diretas
- Perguntas conceituais com respostas instrutivas e contábeis
- Análise de hábitos de compras e compras não registadas
- Categorização rigorosa de poupança (não confundir poupança de carro com transporte)
- Memória persistente e gráficos interativos
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.connection import get_connection

client = TestClient(app)


def _user():
    email = f"copilot_{uuid.uuid4().hex[:8]}@bankao.ao"
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


def test_copilot_simple_question_saldo_direct():
    """Pergunta simples sobre saldo recebe resposta direta em 1-2 linhas."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "qual é o meu saldo?"})
    assert r.status_code == 200
    data = r.json()
    assert "saldo total em Kwanza" in data["reply"]
    assert "Kz" in data["reply"]
    assert len(data["reply"].split("\n")) <= 4


def test_copilot_simple_question_iban_direct():
    """Pergunta sobre IBAN devolve o IBAN diretamente."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "qual é o meu iban?"})
    assert r.status_code == 200
    data = r.json()
    assert "IBAN principal BankAO" in data["reply"]
    assert "AO" in data["reply"]
    assert len(data["reply"]) >= 25


def test_copilot_complex_question_previsao_instrutiva():
    """Pergunta sobre previsão recebe explicação didática e contábil do DCF."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "como funciona a previsão de saldo?"})
    assert r.status_code == 200
    data = r.json()
    assert "Fluxo de Caixa" in data["reply"]
    assert "Entradas" in data["reply"]
    assert "Despesas Operacionais" in data["reply"]
    assert "Poupança" in data["reply"]


def test_copilot_complex_question_deposito_a_prazo():
    """Pergunta sobre depósito a prazo recebe guia instrutivo com taxas e exemplo."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "o que é um depósito a prazo?"})
    assert r.status_code == 200
    data = r.json()
    assert "18,5%" in data["reply"]
    assert "Juro Composto" in data["reply"]
    assert "Exemplo Numérico" in data["reply"]


def test_copilot_regra_50_30_20():
    """Explicação da regra 50/30/20 com metodologia contábil."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "o que é a regra 50/30/20?"})
    assert r.status_code == 200
    data = r.json()
    assert "50%" in data["reply"]
    assert "30%" in data["reply"]
    assert "20%" in data["reply"]


def test_copilot_habitos_de_compra():
    """Análise contabilística de hábitos de compras."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "quais são os meus hábitos de compra?"})
    assert r.status_code == 200
    data = r.json()
    assert "Despesas este mês" in data["reply"] or "hábitos" in data["reply"].lower()


def test_copilot_gasto_poupanca_de_carro_fica_em_poupanca():
    """Registar gasto na poupança de carro deve categorizar estritamente como Poupança."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "registre um gasto de 10mil na poupança de carro"})
    assert r.status_code == 200
    data = r.json()
    assert data["action"] is not None
    assert data["action"]["type"] == "EXPENSE_REGISTERED"   # despesas registam-se logo, sem formulário
    assert data["action"]["category"] == "Poupança"
    assert data["action"]["amount"] == 10000.0
    assert "Poupança" in data["action"]["name"]
    assert "carro" in data["action"]["name"].lower()


def test_copilot_chart_forecast():
    """Geração de gráfico de previsão de saldo."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "gráfico de previsão de saldo"})
    assert r.status_code == 200
    data = r.json()
    assert data["chart"] is not None
    assert data["chart"]["type"] == "forecast"
    assert "Previsão" in data["chart"]["title"]
    assert len(data["chart"]["points"]) >= 6


def test_copilot_memory_persistence():
    """Memória é salva quando o utilizador menciona aspirações ou informações."""
    h = _user()
    r = client.post("/api/ai/chat-v2", headers=h, json={"message": "eu ganho um salário de 350mil kz e quero comprar um carro"})
    assert r.status_code == 200
    
    # Consultar endpoint de memória
    r_mem = client.get("/api/ai/memory", headers=h)
    assert r_mem.status_code == 200
    mem_keys = [m["key"] for m in r_mem.json()["memory"]]
    assert "rendimento_mensal" in mem_keys or "interesse_carro" in mem_keys
