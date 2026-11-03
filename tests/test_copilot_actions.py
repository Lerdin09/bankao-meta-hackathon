# -*- coding: utf-8 -*-
"""
Copilot: a IA prepara, o utilizador conclui.
Cobre os erros reportados: «50mil kz» virava despesa de 2027 Kz, e transferências «por conta» iam parar ao IBAN.
"""
from datetime import date

from backend.ai.intents import analyze_message

HOJE = date(2026, 11, 1)


def ana(msg, pending=None):
    return analyze_message(msg, pending, HOJE)


def test_poupanca_carro_nao_vira_despesa_nem_confunde_ano_com_valor():
    r = ana("criar uma poupança de um carro que eu vou comprar em agosto de 2027 50mil kz")
    assert r["action"] is None and r["pending"]["slots"]["ask"] == "start"      # pergunta quando começar
    r = ana("sem automático", r["pending"])
    a = r["action"]
    assert a["type"] == "CREATE_SAVINGS_GOAL"
    assert a["target"] == 50000.0           # nunca 2027
    assert a["icon_key"] == "car" and a["name"] == "Carro"
    assert a["deadline"] == "2027-08"
    assert a["months"] == 9 and a["monthly"] == 5556.0   # ceil(50000 / 9)
    assert "ainda não foi criada" in r["reply"]


def test_poupanca_pergunta_o_prazo_em_vez_de_inventar():
    r = ana("quero uma poupança para um carro de 50mil kz")
    assert r["action"] is None and r["pending"]["type"] == "CREATE_SAVINGS_GOAL"
    r2 = ana("em agosto de 2027", r["pending"])
    r2 = ana("sem automático", r2["pending"])
    assert r2["action"]["deadline"] == "2027-08" and r2["action"]["target"] == 50000.0
    assert r2["pending"] is None


def test_valores_com_mil_k_e_milhoes():
    assert ana("poupar 1,5 milhões para uma casa em 2 anos")["pending"]["slots"]["target"] == 1_500_000.0
    assert ana("poupança de 50k para uma viagem em dezembro de 2027")["pending"]["slots"]["target"] == 50_000.0
    assert ana("gastei 12.500 kz no almoço")["action"]["amount"] == 12_500.0


def test_transferencia_por_conta_vai_para_conta_interna_e_nao_para_iban():
    r = ana("quero fazer uma transferência por conta de 5000 kz para 004012345678")
    a = r["action"]
    assert a["type"] == "TRANSFER_INTERNAL"
    assert a["to_account_number"] == "004012345678" and a["amount"] == 5000.0
    assert a["fee_amount"] == 50.0 and a["net_amount"] == 4950.0     # 1%
    assert ana("transfere 10000 kz para joao@bankao.ao")["action"]["type"] == "TRANSFER_INTERNAL"


def test_transferencia_sem_destino_pergunta_e_junta_a_resposta():
    r = ana("quero transferir 5000 por conta")
    assert r["action"] is None and "conta BankAO" in r["reply"]
    r2 = ana("0040 1234 5678", r["pending"])
    assert r2["action"]["type"] == "TRANSFER_INTERNAL" and r2["action"]["amount"] == 5000.0


def test_transferencia_iban_mantem_nome_e_taxa_de_2_5():
    r = ana("faça a transferência para AO06004000000000000000000, de 10000KZ, nome: Maria Silva")
    a = r["action"]
    assert a["type"] == "TRANSFER_IBAN" and a["beneficiary_name"] == "Maria Silva"
    assert a["to_iban"] == "AO06004000000000000000000" and a["amount"] == 10000.0
    assert a["fee_amount"] == 250.0 and a["net_amount"] == 9750.0


def test_nunca_inventa_valor_e_perguntas_informativas_seguem_para_o_modelo():
    assert ana("quero depositar")["action"] is None
    for pergunta in ("Como posso enviar uma transferência com IBAN de destino?",
                     "Como faço para depositar fundos na minha conta com Multicaixa Express?",
                     "Quais são as taxas de câmbio actuais para enviar dinheiro a Portugal e Europa?"):
        r = ana(pergunta)
        assert r["action"] is None and r["reply"] is None and r["pending"] is None


def test_pergunta_fora_de_contexto_abandona_o_pedido_pendente():
    r = ana("quero transferir 5000 por conta")
    r2 = ana("como funciona o câmbio?", r["pending"])
    assert r2["action"] is None and r2["pending"] is None and r2["reply"] is None


def test_respostas_nunca_afirmam_que_a_operacao_foi_concluida():
    for msg in ("gastei 15000 kz no supermercado maxi", "regista 25000 kz de combustivel sonangol",
                "transfere 5000 para joao@bankao.ao", "deposita 20000 kz no multicaixa express 923 456 789"):
        reply = ana(msg)["reply"].lower()
        assert "não foi" in reply or "ainda não" in reply
        assert "com sucesso" not in reply


def test_despesa_com_data_relativa():
    a = ana("gastei 3500 ontem no taxi")["action"]
    assert a["type"] == "REGISTER_EXPENSE" and a["date"] == "2026-10-31" and a["category"] == "Transporte"


def test_poupanca_guiada_ate_ao_plano_com_dia_de_debito():
    p, r = None, None
    for msg in ("quero uma poupança, como eu faço?", "de moradia", "uns 150mil",
                "penso em até 15 meses", "dezembro", "5"):
        r = ana(msg, p)
        p = r["pending"]
    a = r["action"]
    assert a["name"] == "Casa" and a["icon_key"] == "home" and a["target"] == 150000.0
    assert a["months"] == 15 and a["monthly"] == 10000.0
    assert a["debit_day"] == 5 and a["start_date"] == "2026-12-05" and a["deadline"] == "2028-02"
    assert r["pending"] is None and "ainda não foi criada" in r["reply"]


def test_poupanca_guiada_perguntas_curtas_e_ordenadas():
    r = ana("quero uma poupança, como eu faço?")
    assert r["pending"]["slots"]["ask"] == "kind" and len(r["reply"]) < 90
    r = ana("de moradia", r["pending"])
    assert r["reply"] == "Quanto custa a casa?"
    r = ana("150000", r["pending"])
    assert r["pending"]["slots"]["ask"] == "months"


def test_poupanca_dia_que_ja_passou_empurra_para_o_mes_seguinte():
    dia20 = date(2026, 11, 20)
    r = analyze_message("quero poupar 120 mil para uma viagem em 12 meses", None, dia20)
    r = analyze_message("novembro", r["pending"], dia20)
    r = analyze_message("5", r["pending"], dia20)             # 5 de novembro já passou
    assert r["action"]["start_date"] == "2026-12-05" and "já passou" in r["reply"]


def test_poupanca_sem_debito_automatico_e_pergunta_fora_do_assunto():
    r = ana("quero uma poupança de carro de 80 mil em 8 meses")
    r = ana("sem débito automático", r["pending"])
    assert "debit_day" not in r["action"] and r["action"]["monthly"] == 10000.0
    r = ana("quero uma poupança de carro de 80 mil em 8 meses")
    r2 = ana("como funciona o câmbio?", r["pending"])           # abandona o fluxo
    assert r2["action"] is None and r2["pending"] is None and r2["reply"] is None


def test_registre_gasto_na_poupanca_de_carro_fica_em_poupanca():
    r = ana("registre um gasto de 10mil na poupança de carro")
    a = r["action"]
    assert a is not None
    assert a["type"] == "REGISTER_EXPENSE"
    assert a["amount"] == 10000.0
    assert a["category"] == "Poupança"
    assert "poupança" in a["name"].lower()
    assert "carro" in a["name"].lower()
    assert "Poupança" in r["reply"]

