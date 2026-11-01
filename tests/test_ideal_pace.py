# -*- coding: utf-8 -*-
"""Linha azul do gráfico do cartão: cálculo do ritmo ideal e proteção contra respostas más da IA."""
from types import SimpleNamespace

from backend.ai import ideal_pace as ip


def _client(content=None, error=None):
    def create(**_kwargs):
        if error:
            raise error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_local_ideal_respeita_orcamento_metas_e_piso():
    assert ip.local_ideal(500000, 300000, 100000)["ideal_spend_month"] == 300000   # limitado pelo orçamento
    assert ip.local_ideal(300000, 300000, 100000)["ideal_spend_month"] == 200000   # sobra depois das metas
    assert ip.local_ideal(100000, 300000, 100000)["ideal_spend_month"] == 90000    # piso de 30 % do orçamento
    assert ip.local_ideal(0, 200000, 50000)["ideal_spend_month"] == 200000         # sem receita usa o orçamento


def test_sem_chave_usa_calculo_local(monkeypatch):
    monkeypatch.setattr(ip, "get_meta_client", lambda: None)
    r = ip.compute_ideal_pace("AOA", 400000, 350000, 300000, [{"name": "Férias", "monthly": 100000}])
    assert r["source"] == "local" and r["ideal_spend_month"] == 300000 and r["status"] == "atencao"


def test_ia_dentro_da_margem_e_aceite(monkeypatch):
    monkeypatch.setattr(ip, "get_meta_client", lambda: _client('{"ideal_spend_month": 270000, "tip": "Corte 10% em lazer."}'))
    r = ip.compute_ideal_pace("AOA", 400000, 350000, 300000, [])
    assert r["source"] == "ai" and r["ideal_spend_month"] == 270000 and r["tip"].startswith("Corte")


def test_ia_com_valor_absurdo_ou_lixo_nao_parte_o_grafico(monkeypatch):
    monkeypatch.setattr(ip, "get_meta_client", lambda: _client('{"ideal_spend_month": 9999999, "tip": "x"}'))
    assert ip.compute_ideal_pace("AOA", 400000, 350000, 300000, [])["ideal_spend_month"] == 300000
    monkeypatch.setattr(ip, "get_meta_client", lambda: _client("isto não é json"))
    assert ip.compute_ideal_pace("AOA", 400000, 350000, 300000, [])["source"] == "local"
    monkeypatch.setattr(ip, "get_meta_client", lambda: _client(error=RuntimeError("rede")))
    assert ip.compute_ideal_pace("AOA", 400000, 350000, 300000, [])["source"] == "local"
