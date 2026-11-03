"""
Ferramentas de Cartões Bancários para a IA do BankAO.
Consulta a tabela `cards` e `card_movements` reais.
"""
from typing import Any, Dict, List, Optional

from backend.database import get_connection


def tool_get_cards(user_id: str) -> Dict[str, Any]:
    """
    Lista todos os cartões (físicos, de crédito, de débito e virtuais) do utilizador autenticado.
    Retorna estado, limites e consumos reais.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.*, a.currency as acc_currency, a.account_number
            FROM cards c
            JOIN accounts a ON a.id = c.account_id
            WHERE c.user_id = ?
            ORDER BY c.created_at ASC
            """,
            (user_id,)
        ).fetchall()

        cards = []
        for r in rows:
            daily_limit = round((r["daily_limit_minor"] or 0) / 100.0, 2)
            monthly_limit = round((r["monthly_limit_minor"] or 0) / 100.0, 2)
            daily_spent = round((r["daily_spent_minor"] or 0) / 100.0, 2)
            monthly_spent = round((r["monthly_spent_minor"] or 0) / 100.0, 2)
            credit_limit = round((r["credit_limit_minor"] or 0) / 100.0, 2)
            credit_used = round((r["credit_used_minor"] or 0) / 100.0, 2)

            cards.append({
                "id": r["id"],
                "label": r["label"] or f"Cartão {r['network'].upper()}",
                "card_type": r["card_type"],
                "network": r["network"],
                "last_four": r["last_four"],
                "cardholder_name": r["cardholder_name"],
                "status": r["status"],
                "is_virtual": bool(r["is_virtual"]),
                "currency": r["currency"] or r["acc_currency"],
                "daily_limit": daily_limit,
                "monthly_limit": monthly_limit,
                "daily_spent": daily_spent,
                "monthly_spent": monthly_spent,
                "credit_limit": credit_limit,
                "credit_used": credit_used
            })

        return {
            "cards_count": len(cards),
            "cards": cards
        }


def tool_get_card_spend_comparison(user_id: str) -> Dict[str, Any]:
    """
    Compara os gastos entre os diferentes cartões do utilizador
    e identifica qual cartão está a gastar mais este mês.
    """
    cards_data = tool_get_cards(user_id)
    cards = cards_data["cards"]

    if not cards:
        return {
            "cards_count": 0,
            "top_card": None,
            "comparison": []
        }

    total_monthly_spent = sum(c["monthly_spent"] for c in cards)
    total_daily_spent = sum(c["daily_spent"] for c in cards)

    comparison = []
    for c in cards:
        pct = round((c["monthly_spent"] / total_monthly_spent) * 100.0, 1) if total_monthly_spent > 0 else 0.0
        comparison.append({
            "card_id": c["id"],
            "label": c["label"],
            "last_four": c["last_four"],
            "network": c["network"],
            "card_type": c["card_type"],
            "status": c["status"],
            "monthly_spent": c["monthly_spent"],
            "daily_spent": c["daily_spent"],
            "monthly_limit": c["monthly_limit"],
            "percent_of_total_spend": pct,
            "currency": c["currency"]
        })

    comparison.sort(key=lambda x: x["monthly_spent"], reverse=True)
    top_card = comparison[0] if comparison else None

    return {
        "cards_count": len(cards),
        "total_monthly_spent": round(total_monthly_spent, 2),
        "total_daily_spent": round(total_daily_spent, 2),
        "top_card": top_card,
        "comparison": comparison
    }
