# -*- coding: utf-8 -*-
"""Investimento no Copilot: pergunta a pergunta; abre o formulário no fim ou quando o cliente pede; ou só a página."""
import pytest

from backend.ai import invest_flow as f

CAT = [
    {"id": "DP-BANKAO-MAX", "name": "Depósito a Prazo Super Rendimento BankAO", "category": "deposito_prazo", "institution": "BankAO",
     "currency": "AOA", "rate_annual": 18.5, "term_months": 12, "min_amount_minor": 10_000_000},
    {"id": "BODIVA-OT-2027", "name": "Obrigações do Tesouro OT-NR 2027", "category": "obrigacoes", "institution": "BODIVA / MinFin",
     "currency": "AOA", "rate_annual": 17.2, "term_months": 24, "min_amount_minor": 25_000_000},
    {"id": "BODIVA-BT-364", "name": "Bilhetes do Tesouro BT 364 Dias", "category": "obrigacoes", "institution": "BODIVA / MinFin",
     "currency": "AOA", "rate_annual": 16.4, "term_months": 12, "min_amount_minor": 10_000_000},
    {"id": "DP-BFA-CRESCENTE", "name": "Depósito Trimestral Crescente BFA", "category": "deposito_prazo", "institution": "Banco BFA",
     "currency": "AOA", "rate_annual": 15.0, "term_months": 3, "min_amount_minor": 5_000_000},
    {"id": "DP-STDBK-USD", "name": "Depósito Moeda Estrangeira USD Standard Bank", "category": "deposito_prazo",
     "institution": "Standard Bank Angola", "currency": "USD", "rate_annual": 4.5, "term_months": 12, "min_amount_minor": 100_000},
]


@pytest.fixture(autouse=True)
def fake_data(monkeypatch):
    monkeypatch.setattr(f, "_catalog", lambda: CAT)
    monkeypatch.setattr(f, "_balance", lambda *a, **k: {"has_account": True, "has_sufficient_funds": True})


def say(msg, pending=None):
    return f.handle_investment_message("u1", msg, pending)


def test_guiado_produto_montante_e_abre_o_formulario_sem_pedir_nome():
    r = say("quero investir")
    assert r["action"] is None and r["pending"]["slots"]["ask"] == "product"
    assert "abrir o formulário" in r["reply"]
    r = say("1", r["pending"])                                   # número da lista
    assert r["action"] is None and r["pending"]["slots"]["ask"] == "amount"
    r = say("500 mil", r["pending"])                             # o nome é opcional: já não se pergunta
    a = r["action"]
    assert a["type"] == "INVESTMENT_APPLY" and r["pending"] is None
    assert a["product_id"] == "DP-BANKAO-MAX" and a["amount"] == 500000.0 and a["notes"] == ""
    assert not a["partial"] and "não foi investido" in r["reply"]


def test_tudo_numa_frase_abre_logo_o_formulario():
    r = say("quero investir 500 mil no depósito super rendimento bankao")
    assert r["pending"] is None and r["action"]["type"] == "INVESTMENT_APPLY"
    assert r["action"]["product_id"] == "DP-BANKAO-MAX" and r["action"]["amount"] == 500000.0


def test_produto_por_nome_ambiguo_pergunta_qual():
    r = say("quero investir num depósito")
    assert r["pending"]["slots"]["ask"] == "product"
    assert set(r["pending"]["slots"]["candidates"]) == {"DP-BANKAO-MAX", "DP-BFA-CRESCENTE", "DP-STDBK-USD"}
    r = say("o depósito", r["pending"])                          # continua ambíguo: volta a perguntar
    assert r["pending"]["slots"]["ask"] == "product" and "mais do que um" in r["reply"]
    r = say("2", r["pending"])                                   # número dentro da lista reduzida
    assert r["pending"]["slots"]["ask"] == "amount" and r["pending"]["slots"]["product_id"] == "DP-BFA-CRESCENTE"


def test_nome_mais_preciso_resolve_a_ambiguidade():
    r = say("quero investir num depósito")
    r = say("depósito a prazo bankao", r["pending"])
    assert r["pending"]["slots"]["product_id"] == "DP-BANKAO-MAX" and r["pending"]["slots"]["ask"] == "amount"


def test_obrigacoes_do_tesouro_escolhe_a_ot_e_nao_os_bilhetes():
    r = say("quero investir em obrigações do tesouro")
    assert r["pending"]["slots"]["product_id"] == "BODIVA-OT-2027"


def test_abrir_formulario_a_meio_abre_com_o_que_ha():
    r = say("quero investir 300 mil")
    r = say("abre o formulário", r["pending"])
    a = r["action"]
    assert a["type"] == "INVESTMENT_APPLY" and a["partial"] and a["product_id"] is None


def test_abrir_formulario_sem_produto_abre_o_catalogo():
    r = say("quero investir")
    r = say("pode abrir já", r["pending"])
    assert r["action"]["type"] == "INVESTMENT_APPLY" and r["action"]["product_id"] is None


def test_abrir_a_pagina_abre_so_a_pagina():
    r = say("quero investir 300 mil no depósito super rendimento bankao")
    r = say("abre a página de investimentos", r["pending"])
    assert r["action"]["type"] == "OPEN_INVESTMENTS" and r["pending"] is None
    r = say("abre a página de investimentos")                    # também fora do fluxo
    assert r["action"]["type"] == "OPEN_INVESTMENTS"


def test_montante_abaixo_do_minimo_volta_a_perguntar():
    r = say("quero investir 50 mil no depósito super rendimento bankao")
    assert r["pending"]["slots"]["ask"] == "amount" and "mínimo" in r["reply"]
    r = say("200 mil", r["pending"])
    assert r["action"]["type"] == "INVESTMENT_APPLY" and r["action"]["amount"] == 200000.0


def test_cancelar():
    r = say("quero investir")
    r = say("cancela", r["pending"])
    assert r["action"] is None and r["pending"] is None


def test_moeda_errada_no_produto_em_dolares():
    r = say("quero investir no depósito usd standard bank")
    assert r["pending"]["slots"]["ask"] == "amount"
    r = say("500 mil kz", r["pending"])
    assert "USD" in r["reply"] and r["pending"]["slots"]["ask"] == "amount"


def test_perguntas_e_consultas_nao_entram_no_fluxo():
    for m in ["como posso investir?", "qual o melhor investimento para mim", "quero ver os meus investimentos",
              "recomenda um investimento", "onde devo investir 100 mil", "o que é um ETF?"]:
        assert say(m) is None, m


def test_pergunta_a_meio_abandona_o_fluxo():
    r = say("quero investir")
    assert say("qual é o meu saldo?", r["pending"]) is None


# ---- Pedidos completos numa só frase: nada de listas nem recomendações ----
def test_bodiva_100mil_para_o_filho_abre_logo_o_formulario():
    """«Bodiva 18,5» não existe: 100 mil só chega para o BT 364 (mín. 100 mil) → abre o formulário e avisa da taxa."""
    for m in ["quero fazer um investimento de 100mil, Bodiva 18,5 para o meu filho",
              "quero investir 100 mil na Bodiva a 18,5% para o meu filho",
              "invisto 100mil no bodiva 18,5, para o meu filho"]:
        r = say(m)
        a = r["action"]
        assert a and a["type"] == "INVESTMENT_APPLY" and r["pending"] is None, m
        assert a["product_id"] == "BODIVA-BT-364" and a["amount"] == 100000.0 and a["notes"] == "Para o meu filho", m
        assert not a["partial"] and "18,5%" in r["reply"] and "16,4%" in r["reply"], m


def test_taxa_certa_escolhe_o_produto():
    r = say("quero investir 200 mil a 18,5% para a reforma")
    assert r["action"]["product_id"] == "DP-BANKAO-MAX" and r["action"]["notes"] == "Para a reforma"
    assert "Disse" not in r["reply"]                              # taxa coincide: sem aviso


def test_bodiva_com_montante_que_serve_a_ambos_pergunta_so_entre_esses():
    r = say("quero investir 500 mil na bodiva")
    assert r["action"] is None and set(r["pending"]["slots"]["candidates"]) == {"BODIVA-OT-2027", "BODIVA-BT-364"}


def test_para_nao_confunde_com_verbos():
    assert f._purpose_name("quero investir para ver o que acontece") is None
    assert f._purpose_name("investir 100 mil para o meu filho no BT 364") == "Para o meu filho"
