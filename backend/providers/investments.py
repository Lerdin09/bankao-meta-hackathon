"""
Fornecedores de dados de investimento (bancos, corretoras, bolsa).

Cada produto do catálogo indica a sua `provider_api` (ex.: open_banking, bodiva,
market_data). Este módulo expõe um adaptador por fornecedor com a mesma interface:

    fetch_update(investment: dict, today: date) -> ProviderUpdate

No modo sandbox (o atual) os adaptadores são DETERMINÍSTICOS e calculados
localmente: juros pro-rata para depósitos/obrigações, variação de cotação
reprodutível por dia para ETFs/ações e dividendos trimestrais para fundos.
Para ligar uma API real, basta substituir o corpo do adaptador respetivo (ou
registar um novo com `register_provider`) — o resto da aplicação não muda.
"""
from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class ProviderUpdate:
    new_value_minor: int            # valor atual de mercado/contabilístico
    accumulated_yield_minor: int    # rendimento acumulado desde o início
    source: str                     # fornecedor que respondeu
    event: str                      # 'juros' | 'cotacao' | 'dividendo'
    note: str = ""
    new_rate_annual: Optional[float] = None   # taxa atualizada, se o fornecedor a alterou


def _days_held(inv: dict, today: datetime.date) -> int:
    """Dias decorridos desde o início; os juros param na data de vencimento."""
    try:
        start = datetime.date.fromisoformat(inv["start_date"])
    except Exception:
        start = today - datetime.timedelta(days=30)
    mat = inv.get("maturity_date")
    if mat:
        try:
            today = min(today, datetime.date.fromisoformat(mat))
        except Exception:
            pass
    return max(1, (today - start).days)


def _accrued(inv: dict, today: datetime.date) -> int:
    rate = float(inv.get("rate_annual") or 0.0)
    principal = int(inv["amount_invested_minor"])
    return int(round(principal * (rate / 100.0) * (_days_held(inv, today) / 365.0)))


def _daily_drift(inv: dict, today: datetime.date) -> float:
    """Variação diária reprodutível (−0,6% … +1,2%): a mesma data dá o mesmo valor."""
    h = hashlib.sha256(f"{inv['id']}|{today.isoformat()}".encode()).digest()
    unit = int.from_bytes(h[:4], "big") / 0xFFFFFFFF  # 0..1
    return -0.006 + unit * 0.018


def _fixed_income(inv: dict, today: datetime.date, source: str) -> ProviderUpdate:
    accrued = _accrued(inv, today)
    return ProviderUpdate(
        new_value_minor=int(inv["amount_invested_minor"]) + accrued,
        accumulated_yield_minor=accrued,
        source=source,
        event="juros",
        note="Juros corridos pro-rata atualizados",
    )


def _market(inv: dict, today: datetime.date, source: str) -> ProviderUpdate:
    cur = int(inv["current_value_minor"])
    floor = int(inv["amount_invested_minor"] * 0.70)
    new_val = max(int(round(cur * (1.0 + _daily_drift(inv, today)))), floor)
    return ProviderUpdate(
        new_value_minor=new_val,
        accumulated_yield_minor=max(0, new_val - int(inv["amount_invested_minor"])),
        source=source,
        event="cotacao",
        note="Cotação de mercado atualizada",
    )


def _fund(inv: dict, today: datetime.date, source: str) -> ProviderUpdate:
    accrued = _accrued(inv, today)
    return ProviderUpdate(
        new_value_minor=int(inv["amount_invested_minor"]) + accrued,
        accumulated_yield_minor=accrued,
        source=source,
        event="dividendo",
        note="Rendimento / dividendo do fundo atualizado",
    )


def _by_category(source: str) -> Callable[[dict, datetime.date], ProviderUpdate]:
    def run(inv: dict, today: datetime.date) -> ProviderUpdate:
        cat = inv.get("category")
        if cat in ("deposito_prazo", "obrigacoes"):
            return _fixed_income(inv, today, source)
        if cat in ("etf", "acoes"):
            return _market(inv, today, source)
        return _fund(inv, today, source)
    return run


_REGISTRY: Dict[str, Callable[[dict, datetime.date], ProviderUpdate]] = {
    "open_banking": _by_category("Open Banking"),
    "bodiva": _by_category("BODIVA"),
    "market_data": _by_category("Market Data"),
    "manual": _by_category("Registo manual"),
}


def settlement_value(inv: dict) -> int:
    """Valor final (centavos) a liquidar no vencimento.

    Rendimento fixo/fundos: capital + juros pro-rata até à data de vencimento (e não mais).
    Ações/ETFs não têm juro fixo: liquidam ao valor de mercado atual.
    """
    if inv.get("category") in ("etf", "acoes"):
        return int(inv["current_value_minor"])
    mat = inv.get("maturity_date")
    try:
        at = datetime.date.fromisoformat(mat)
    except Exception:
        return int(inv["current_value_minor"])
    return int(inv["amount_invested_minor"]) + _accrued(inv, at)


def register_provider(name: str, fn: Callable[[dict, datetime.date], ProviderUpdate]) -> None:
    """Regista (ou substitui) o adaptador de um fornecedor — ponto de ligação a APIs reais."""
    _REGISTRY[name] = fn


def fetch_update(inv: dict, provider_api: Optional[str] = None,
                 today: Optional[datetime.date] = None) -> ProviderUpdate:
    """Pede ao fornecedor do investimento os valores atualizados."""
    today = today or datetime.date.today()
    adapter = _REGISTRY.get((provider_api or "manual").lower(), _REGISTRY["manual"])
    return adapter(inv, today)
