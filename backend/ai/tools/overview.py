"""
Ferramentas de leitura adicionais do Copilot: resumo financeiro, metas de poupança,
compras ainda por registar e gráficos inline. Só leem dados do utilizador autenticado.
"""
from typing import Any, Dict, Optional

from backend.database import get_connection

CHART_TYPES = ("donut_expenses_month", "line_expenses_months", "bar_categories_period", "balance_forecast")


def tool_get_financial_snapshot(user_id: str) -> Dict[str, Any]:
    """Foto geral: saldos, despesas do mês, maiores categorias, metas, investimentos e o que o cliente já contou."""
    from backend.ai.copilot_v2 import build_user_context

    ctx = build_user_context(user_id)
    return {
        "user_name": ctx.get("user_name"),
        "accounts": ctx.get("accounts", []),
        "total_aoa": ctx.get("total_aoa", 0.0),
        "monthly_expenses": ctx.get("monthly_expenses", 0.0),
        "top_categories_3_months": ctx.get("top_categories", []),
        "savings_goals": ctx.get("savings_goals", []),
        "investments": ctx.get("investments", []),
        "customer_notes": ctx.get("memory", {}),
    }


def tool_get_savings_goals(user_id: str) -> Dict[str, Any]:
    """Metas de poupança do cliente com progresso e prazo."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, target_minor, saved_minor, monthly_minor, deadline, status, currency "
            "FROM savings_goals WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    goals = []
    for r in rows:
        target = r["target_minor"] / 100.0
        saved = r["saved_minor"] / 100.0
        goals.append({
            "name": r["name"],
            "target": round(target, 2),
            "saved": round(saved, 2),
            "remaining": round(max(0.0, target - saved), 2),
            "percent": round(saved / target * 100, 1) if target else 0.0,
            "monthly": round(r["monthly_minor"] / 100.0, 2),
            "deadline": r["deadline"],
            "status": r["status"],
            "currency": r["currency"],
        })
    return {"count": len(goals), "goals": goals}


def tool_get_unrecorded_purchases(user_id: str) -> Dict[str, Any]:
    """Compras/pagamentos com cartão que ainda não estão nas Despesas (usar SÓ quando o cliente pergunta por isso)."""
    from backend.ai.copilot_v2 import find_unrecorded_expenses

    items = find_unrecorded_expenses(user_id, limit=8)
    return {"count": len(items), "purchases": items}


def tool_show_chart(user_id: str, chart_type: str, month: Optional[str] = None, months: Optional[int] = None) -> Dict[str, Any]:
    """
    Gera um gráfico interativo para mostrar na conversa.
    Devolve `chart` (para o ecrã) e um resumo curto que o modelo pode usar para comentar.
    """
    from backend.ai.copilot_v2 import get_chart_data

    if chart_type not in CHART_TYPES:
        return {"error": f"Tipo de gráfico inválido. Use um de: {', '.join(CHART_TYPES)}."}
    params: Dict[str, Any] = {}
    if month:
        params["month"] = month
    if months:
        params["months"] = max(2, min(int(months), 12))
    chart = get_chart_data(user_id, chart_type, params)
    if not chart:
        return {"has_data": False, "message": "Não há dados suficientes para este gráfico."}
    summary: Dict[str, Any] = {"has_data": True, "chart": chart, "title": chart.get("title")}
    if "total" in chart:
        summary["total"] = chart["total"]
    if chart.get("note"):
        summary["note"] = chart["note"]
    return summary


MONTHS_PT_FULL = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]


def tool_get_financial_projection(
    user_id: str,
    months_ahead: int = 3,
    target_date: Optional[str] = None,
    expense_multiplier: float = 1.0,
    monthly_savings_extra: float = 0.0,
    include_chart: bool = False
) -> Dict[str, Any]:
    """
    Calcula detalhada e matematicamente a projeção financeira futura do cliente.
    Trata separadamente:
    - Previsão de Saldo líquido em contas
    - Metas de Poupança acumuladas
    - Carteira de Investimentos e juros gerados
    - Património Líquido Total
    """
    import datetime, re
    today = datetime.date.today()
    try:
        target_months = max(1, int(float(months_ahead)))
    except (ValueError, TypeError):
        target_months = 6
    target_label = f"daqui a {target_months} meses"

    if target_date:
        td_lower = target_date.strip().lower()
        target_year = today.year
        y_match = re.search(r"\b(202\d)\b", td_lower)
        if y_match:
            target_year = int(y_match.group(1))

        matched_m = None
        for idx, m_name in enumerate(MONTHS_PT_FULL, 1):
            if m_name.lower() in td_lower:
                matched_m = idx
                break

        if matched_m:
            target_months = max(1, (target_year - today.year) * 12 + (matched_m - today.month))
            target_label = f"{MONTHS_PT_FULL[matched_m - 1]} de {target_year}"
        elif "final de 2027" in td_lower or "fim de 2027" in td_lower:
            target_months = max(1, (2027 - today.year) * 12 + (12 - today.month))
            target_label = "Dezembro de 2027 (final de 2027)"
        elif "final de 2026" in td_lower or "fim de 2026" in td_lower:
            target_months = max(1, (2026 - today.year) * 12 + (12 - today.month))
            target_label = "Dezembro de 2026 (final de 2026)"

    target_cal_month = ((today.month - 1 + target_months) % 12) + 1
    target_cal_year = today.year + ((today.month - 1 + target_months) // 12)
    end_month_label = f"{MONTHS_PT_FULL[target_cal_month - 1]} de {target_cal_year}"
    if not target_date:
        target_label = f"{target_label} ({end_month_label})"

    with get_connection() as conn:
        acc_bal_minor = conn.execute("""
            SELECT COALESCE(SUM(le.amount_minor), 0)
            FROM accounts a
            LEFT JOIN ledger_entries le ON le.account_id = a.id
            WHERE a.user_id = ? AND a.currency = 'AOA'
        """, (user_id,)).fetchone()[0]
        current_acc_balance = round(float(acc_bal_minor) / 100.0, 2)

        goals = conn.execute("""
            SELECT name, target_minor, saved_minor, monthly_minor, deadline, status
            FROM savings_goals WHERE user_id = ? AND status != 'completed'
        """, (user_id,)).fetchall()

        current_saved_goals = round(sum(g["saved_minor"] for g in goals) / 100.0, 2)
        monthly_savings_debits = round(sum(g["monthly_minor"] for g in goals) / 100.0, 2)

        invs = conn.execute("""
            SELECT name, category, amount_invested_minor, current_value_minor,
                   accumulated_yield_minor, rate_annual, maturity_date
            FROM user_investments WHERE user_id = ? AND status = 'ativo'
        """, (user_id,)).fetchall()

        current_invested = round(sum(i["amount_invested_minor"] for i in invs) / 100.0, 2)
        current_inv_value = round(sum(i["current_value_minor"] for i in invs) / 100.0, 2)
        current_yield = round(sum(i["accumulated_yield_minor"] for i in invs) / 100.0, 2)

        avg_in_minor = conn.execute("""
            SELECT COALESCE(AVG(monthly_total), 0) FROM (
                SELECT strftime('%Y-%m', le.created_at) as m, SUM(le.amount_minor) as monthly_total
                FROM ledger_entries le
                JOIN accounts a ON a.id = le.account_id AND a.user_id = ?
                WHERE le.amount_minor > 0
                GROUP BY m ORDER BY m DESC LIMIT 3
            )
        """, (user_id,)).fetchone()[0]
        monthly_income_avg = round(float(avg_in_minor) / 100.0, 2)
        if monthly_income_avg <= 0:
            monthly_income_avg = 400000.0

        avg_out_minor = conn.execute("""
            SELECT COALESCE(AVG(monthly_total), 0) FROM (
                SELECT strftime('%Y-%m', expense_date) as m, SUM(amount_minor) as monthly_total
                FROM expenses WHERE user_id = ? AND origin != 'savings'
                GROUP BY m ORDER BY m DESC LIMIT 3
            )
        """, (user_id,)).fetchone()[0]
        base_monthly_expenses = round(float(avg_out_minor) / 100.0, 2)
        if base_monthly_expenses <= 0:
            all_out = conn.execute("""
                SELECT COALESCE(AVG(monthly_total), 0) FROM (
                    SELECT strftime('%Y-%m', expense_date) as m, SUM(amount_minor) as monthly_total
                    FROM expenses WHERE user_id = ?
                    GROUP BY m ORDER BY m DESC LIMIT 3
                )
            """, (user_id,)).fetchone()[0]
            base_monthly_expenses = round(float(all_out) / 100.0, 2)

    effective_monthly_expenses = round(base_monthly_expenses * expense_multiplier, 2)
    monthly_net_unallocated = round(monthly_income_avg - effective_monthly_expenses - monthly_savings_debits - monthly_savings_extra, 2)

    projected_acc_balance = round(current_acc_balance + (monthly_net_unallocated * target_months), 2)
    projected_saved_goals = round(current_saved_goals + ((monthly_savings_debits + monthly_savings_extra) * target_months), 2)

    projected_inv_details = []
    projected_inv_total = 0.0
    projected_inv_yield = 0.0

    for i in invs:
        c_val = float(i["current_value_minor"]) / 100.0
        inv_amt = float(i["amount_invested_minor"]) / 100.0
        rate = float(i["rate_annual"] or 18.0)
        monthly_r = (rate / 100.0) / 12.0
        future_val = round(c_val * ((1 + monthly_r) ** target_months), 2)
        yield_total = round(future_val - inv_amt, 2)

        projected_inv_total += future_val
        projected_inv_yield += yield_total
        projected_inv_details.append({
            "name": i["name"],
            "current_value": c_val,
            "projected_value": future_val,
            "projected_yield": yield_total,
            "rate_annual": rate,
            "maturity_date": i["maturity_date"]
        })

    projected_inv_total = round(projected_inv_total, 2)
    projected_inv_yield = round(projected_inv_yield, 2)

    current_total_net_worth = round(current_acc_balance + current_saved_goals + current_inv_value, 2)
    projected_total_net_worth = round(projected_acc_balance + projected_saved_goals + projected_inv_total, 2)
    net_worth_growth = round(projected_total_net_worth - current_total_net_worth, 2)
    net_worth_growth_pct = round((net_worth_growth / current_total_net_worth * 100.0), 1) if current_total_net_worth > 0 else 0.0

    chart_data = None
    if include_chart or target_months in (6, 12):
        points = []
        running_bal = current_acc_balance
        for step in range(min(12, max(6, target_months))):
            m_idx = ((today.month - 1 + step) % 12)
            lbl = MONTHS_PT_FULL[m_idx][:3]
            running_bal += monthly_net_unallocated
            points.append({"label": lbl, "value": round(running_bal, 2)})
        chart_data = {
            "type": "forecast",
            "title": f"Evolução Prevista do Saldo ({len(points)} meses)",
            "current": current_acc_balance,
            "points": points,
            "note": f"Fluxo líquido estimado: {monthly_net_unallocated:+,.2f} Kz/mês"
        }

    return {
        "as_of_date": today.isoformat(),
        "target_date_label": target_label,
        "end_month_label": end_month_label,
        "months_ahead": target_months,
        "scenario": {
            "expense_multiplier": expense_multiplier,
            "expense_variation_pct": round((expense_multiplier - 1.0) * 100, 1),
            "monthly_income_avg": monthly_income_avg,
            "base_monthly_expenses": base_monthly_expenses,
            "effective_monthly_expenses": effective_monthly_expenses,
            "monthly_savings_debits": monthly_savings_debits,
            "monthly_savings_extra": monthly_savings_extra,
            "monthly_net_unallocated": monthly_net_unallocated
        },
        "current_position": {
            "accounts_balance": current_acc_balance,
            "savings_goals_saved": current_saved_goals,
            "investments_value": current_inv_value,
            "investments_yield_earned": current_yield,
            "total_net_worth": current_total_net_worth
        },
        "projection": {
            "projected_accounts_balance": projected_acc_balance,
            "projected_savings_goals_saved": projected_saved_goals,
            "projected_investments_value": projected_inv_total,
            "projected_investments_yield": projected_inv_yield,
            "projected_total_net_worth": projected_total_net_worth,
            "net_worth_growth": net_worth_growth,
            "net_worth_growth_pct": net_worth_growth_pct,
            "investments_details": projected_inv_details
        },
        "chart": chart_data
    }
