"""
Ferramentas de Investimentos e Simulações Financeiras para a IA do BankAO.
Consulta `user_investments` e `investment_products` reais e executa cálculos determinísticos.
"""
import math
from typing import Any, Dict, List, Optional

from backend.database import get_connection


def tool_get_investments_portfolio(user_id: str) -> Dict[str, Any]:
    """
    Consulta a carteira de investimentos do utilizador autenticado.
    Identifica valor investido, valor atual, rendimentos e quais produtos estão a render mais.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT ui.*, ip.name as prod_name, ip.category as prod_cat, ip.institution as prod_inst,
                   ip.rate_annual as prod_rate, ip.risk_level as prod_risk
            FROM user_investments ui
            LEFT JOIN investment_products ip ON ip.id = ui.product_id
            WHERE ui.user_id = ? AND ui.status = 'ativo'
            ORDER BY ui.current_value_minor DESC
            """,
            (user_id,)
        ).fetchall()

        total_invested = 0.0
        total_current = 0.0
        total_yield = 0.0
        positions = []

        for r in rows:
            invested_minor = r["amount_invested_minor"] if "amount_invested_minor" in r.keys() else r["invested_minor"]
            invested = round(invested_minor / 100.0, 2)
            current_minor = r["current_value_minor"]
            current = round(current_minor / 100.0, 2)
            yield_minor = r["accumulated_yield_minor"] if "accumulated_yield_minor" in r.keys() else r["yield_earned_minor"]
            y_amt = round(yield_minor / 100.0, 2)
            y_pct = round(((current - invested) / invested) * 100.0, 2) if invested > 0 else 0.0

            total_invested += invested
            total_current += current
            total_yield += y_amt

            name = r["name"] or r["prod_name"] or "Investimento"
            positions.append({
                "id": r["id"],
                "name": name,
                "category": r["category"] or r["prod_cat"],
                "institution": r["institution"] or r["prod_inst"],
                "currency": r["currency"],
                "invested_amount": invested,
                "current_value": current,
                "yield_earned": y_amt,
                "yield_percentage": y_pct,
                "rate_annual": r["rate_annual"] or r["prod_rate"],
                "start_date": r["start_date"],
                "maturity_date": r["maturity_date"]
            })

        # Ordenar por rentabilidade percentual para ver quais rendem mais
        top_yielding = sorted(positions, key=lambda p: p["yield_percentage"], reverse=True)

        return {
            "has_investments": len(positions) > 0,
            "total_positions": len(positions),
            "total_invested": round(total_invested, 2),
            "total_current_value": round(total_current, 2),
            "total_yield_earned": round(total_yield, 2),
            "positions": positions,
            "best_performing": top_yielding[0] if top_yielding else None
        }


def tool_get_investment_catalog(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Consulta o catálogo de produtos de investimento reais disponíveis no BankAO
    (Depósitos a Prazo até 18.5%, Obrigações BODIVA, Bilhetes do Tesouro, ETFs globais).
    """
    with get_connection() as conn:
        query = "SELECT * FROM investment_products WHERE is_active = 1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY rate_annual DESC, min_amount_minor ASC"

        rows = conn.execute(query, params).fetchall()
        products = []
        for r in rows:
            products.append({
                "id": r["id"],
                "name": r["name"],
                "category": r["category"],
                "institution": r["institution"],
                "currency": r["currency"],
                "rate_annual": r["rate_annual"],
                "term_months": r["term_months"],
                "min_amount": round(r["min_amount_minor"] / 100.0, 2),
                "risk_level": r["risk_level"],
                "liquidity": r["liquidity"],
                "description": r["description"]
            })

        return {
            "products_count": len(products),
            "products": products
        }


def tool_simulate_investment(
    initial_amount: float,
    monthly_contribution: float = 0.0,
    months: int = 12,
    annual_rate: float = 18.5
) -> Dict[str, Any]:
    """
    Simulação determinística e precisa de juros compostos.
    Calcula exatamente o capital final, total depositado e total ganho em juros.
    """
    initial_amount = max(0.0, float(initial_amount))
    monthly_contribution = max(0.0, float(monthly_contribution))
    months = min(max(1, int(months)), 360)
    annual_rate = max(0.0, float(annual_rate))

    monthly_rate = (annual_rate / 100.0) / 12.0

    balance = initial_amount
    total_deposited = initial_amount
    evolution = []

    for m in range(1, months + 1):
        interest_this_month = balance * monthly_rate
        balance += interest_this_month + monthly_contribution
        total_deposited += monthly_contribution
        if m in (1, 3, 6, 12, 24, 36) or m == months:
            evolution.append({
                "month": m,
                "balance": round(balance, 2),
                "total_deposited": round(total_deposited, 2),
                "total_interest": round(balance - total_deposited, 2)
            })

    total_interest = round(balance - total_deposited, 2)

    return {
        "initial_amount": initial_amount,
        "monthly_contribution": monthly_contribution,
        "months": months,
        "annual_rate": annual_rate,
        "final_balance": round(balance, 2),
        "total_deposited": round(total_deposited, 2),
        "total_interest_earned": total_interest,
        "roi_percentage": round((total_interest / total_deposited) * 100.0, 2) if total_deposited > 0 else 0.0,
        "evolution_checkpoints": evolution
    }
