"""
Ritmo ideal — linha azul do gráfico do cartão.

Dado o que a pessoa costuma receber, gastar e poupar, calcula quanto devia gastar por mês
para cumprir as metas de poupança. Com chave da Meta Model API, o modelo propõe o valor e
escreve uma dica; sem chave (ou se a resposta não for válida) usa-se o cálculo local, que é
também o limite de segurança: a IA nunca pode fugir dele por mais de uma margem pequena.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.ai.client import get_meta_client
from backend.core.config import settings

logger = logging.getLogger("bankao.ideal_pace")

# Margem em que a IA pode afastar-se do cálculo local (±25 %)
AI_MARGIN = 0.25


def _num(value: Any) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0.0
    return n if n == n and abs(n) != float("inf") else 0.0


def local_ideal(income_month: float, budget_month: float, goals_month: float) -> Dict[str, float]:
    """
    Gasto mensal ideal = o que sobra depois de pagar as metas, nunca acima do orçamento
    definido e nunca abaixo de 30 % dele (ninguém vive de zero).
    """
    income, budget, goals = max(0.0, income_month), max(0.0, budget_month), max(0.0, goals_month)
    if income <= 0:
        ideal = budget
    else:
        room = income - goals
        ideal = min(budget, room) if budget > 0 else room
    floor = 0.3 * budget if budget > 0 else 0.0
    ideal = max(floor, ideal, 0.0)
    return {"ideal_spend_month": round(ideal, 2), "savings_month": round(max(0.0, income - ideal), 2)}


def _status(expense_month: float, ideal_month: float) -> str:
    if ideal_month <= 0:
        return "sem-dados"
    ratio = expense_month / ideal_month
    return "dentro" if ratio <= 1.0 else ("atencao" if ratio <= 1.2 else "acima")


def _local_tip(status: str, currency: str, expense: float, ideal: float, goals: List[dict]) -> str:
    fmt = lambda v: f"{v:,.0f}".replace(",", ".") + f" {currency}"
    first = next((g.get("name") for g in goals if g.get("name")), None)
    if status == "dentro":
        base = f"Está dentro do ritmo: gasta cerca de {fmt(expense)} por mês e o ideal é até {fmt(ideal)}."
        return base + (f" Continue assim para chegar a «{first}»." if first else "")
    if status in ("atencao", "acima"):
        diff = max(0.0, expense - ideal)
        base = f"Está a gastar mais {fmt(diff)} por mês do que o ideal ({fmt(ideal)})."
        return base + (f" Reduzir este valor aproxima-o de «{first}»." if first else " Rever as despesas maiores ajuda.")
    return "Ainda há poucos movimentos. Com mais histórico, o ritmo ideal fica mais preciso."


def _extract_json(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def compute_ideal_pace(
    currency: str,
    income_month: float,
    expense_month: float,
    budget_month: float,
    goals: List[dict],
) -> Dict[str, Any]:
    currency = (currency or "AOA").upper()[:3]
    goals = [g for g in (goals or []) if isinstance(g, dict)][:12]
    goals_month = sum(max(0.0, _num(g.get("monthly"))) for g in goals)
    base = local_ideal(income_month, budget_month, goals_month)
    ideal = base["ideal_spend_month"]
    tip: Optional[str] = None
    source = "local"

    client = get_meta_client()
    if client and (income_month > 0 or budget_month > 0):
        prompt = (
            "Dados mensais do cliente (valores em {cur}):\n"
            "- Recebe: {inc:.0f}\n- Gasta: {exp:.0f}\n- Orçamento definido: {bud:.0f}\n"
            "- Metas de poupança: {goals}\n- Cálculo base do gasto ideal: {ideal:.0f}\n\n"
            "Propõe o gasto mensal ideal para cumprir as metas sem sufocar o dia a dia. "
            "Responde SÓ com JSON: {{\"ideal_spend_month\": número, \"tip\": \"uma dica curta em português, até 200 caracteres\"}}"
        ).format(
            cur=currency, inc=income_month, exp=expense_month, bud=budget_month, ideal=ideal,
            goals=json.dumps([{k: g.get(k) for k in ("name", "target", "saved", "monthly", "deadline")} for g in goals],
                             ensure_ascii=False),
        )
        try:
            res = client.chat.completions.create(
                model=settings.MODEL_NAME,
                messages=[
                    {"role": "system", "content": "És o BankAO Copilot. Respondes sempre em português e apenas no formato pedido."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
                temperature=0.2,
            )
            data = _extract_json(res.choices[0].message.content or "")
            if data:
                proposed = _num(data.get("ideal_spend_month"))
                lo, hi = ideal * (1 - AI_MARGIN), ideal * (1 + AI_MARGIN)
                if proposed > 0 and (ideal <= 0 or lo <= proposed <= hi):
                    ideal, source = round(proposed, 2), "ai"
                text = str(data.get("tip") or "").strip()
                if text:
                    tip = text[:240]
                    source = "ai"
        except Exception as exc:  # a IA nunca pode partir o gráfico
            logger.error("Erro na Meta Model API (ideal_pace): %s", exc)

    status = _status(expense_month, ideal)
    return {
        "ideal_spend_month": ideal,
        "savings_month": round(max(0.0, income_month - ideal), 2),
        "status": status,
        "tip": tip or _local_tip(status, currency, expense_month, ideal, goals),
        "source": source,
        "model": settings.MODEL_NAME if source == "ai" else "local",
    }
