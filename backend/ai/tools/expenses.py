"""
Ferramentas de Despesas e Orçamentos para a IA do BankAO.
Consulta a tabela `expenses` real, orçamentos, movimentos bancários e comerciantes.
"""
import calendar
import datetime
import re
from typing import Any, Dict, List, Optional

from backend.database import get_connection

ONLINE_KEYWORDS = [
    "online", "amazon", "aliexpress", "ebay", "netflix", "spotify", "apple", "google",
    "uber", "glovo", "unitel net", "multicaixa express", "loja virtual", "steam", "playstation"
]

DISCRETIONARY_CATEGORIES = [
    "restaurantes", "restaurante", "lazer", "eletrónica", "eletronica", "vestuário", "vestuario", "entretenimento", "jogos"
]

ESSENTIAL_CATEGORIES = [
    "habitação", "habitacao", "alimentação", "alimentacao", "transporte", "saúde", "saude", "telecomunicações", "telecomunicacoes", "educação", "educacao"
]


def tool_get_expenses_analysis(
    user_id: str,
    category: Optional[str] = None,
    period: str = "this_month",
    months_count: int = 1,
    min_amount: Optional[float] = None,
    order_by: str = "date_desc",
    limit: Optional[int] = None,
    exclude_savings: bool = False
) -> Dict[str, Any]:
    """
    Analisa as despesas reais do utilizador.
    Suporta filtro por categoria, período temporal alargado (semana, mês específico, ano),
    valor mínimo, ordenação por montante ou data, e distinção entre consumo e afetação a poupança.
    """
    today = datetime.date.today()
    period_lower = (period or "").strip().lower()

    months_names = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    months_map = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
        "abril": 4, "maio": 5, "junho": 6, "julho": 7,
        "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
    }

    matched_month = None
    for m_name, m_num in months_map.items():
        if m_name in period_lower:
            matched_month = m_num
            break

    if matched_month:
        year = today.year
        y_match = re.search(r"\b(202\d)\b", period_lower)
        if y_match:
            year = int(y_match.group(1))
        last_day = calendar.monthrange(year, matched_month)[1]
        start_date = f"{year}-{matched_month:02d}-01"
        end_date = f"{year}-{matched_month:02d}-{last_day:02d}"
        period_label = f"{months_names[matched_month-1]} de {year}"
    elif re.match(r"^\d{4}-\d{2}$", period_lower):
        parts = period_lower.split("-")
        year = int(parts[0])
        m_num = int(parts[1])
        last_day = calendar.monthrange(year, m_num)[1]
        start_date = f"{year}-{m_num:02d}-01"
        end_date = f"{year}-{m_num:02d}-{last_day:02d}"
        period_label = f"{m_num:02d}/{year}"
    elif period_lower in ("last_week", "ultima_semana", "última semana", "last_7_days", "ultimos_7_dias", "semana"):
        start_date = (today - datetime.timedelta(days=7)).isoformat()
        end_date = today.isoformat()
        period_label = f"última semana (desde {(today - datetime.timedelta(days=7)).strftime('%d/%m')})"
    elif period_lower in ("this_week", "esta_semana"):
        start_date = (today - datetime.timedelta(days=today.weekday())).isoformat()
        end_date = today.isoformat()
        period_label = "esta semana"
    elif period_lower in ("this_year", "este_ano", "ano", "desde_janeiro", "ano_atual", "2026"):
        start_date = f"{today.year}-01-01"
        end_date = today.isoformat()
        period_label = f"ano de {today.year}"
    elif period_lower in ("all", "tudo", "historico", "historico_completo", "todos"):
        start_date = "2020-01-01"
        end_date = today.isoformat()
        period_label = "todo o histórico"
    elif period_lower == "this_month":
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat()
        period_label = f"este mês ({today.strftime('%m/%Y')})"
    elif period_lower in ("last_month", "mes_passado", "mês passado"):
        first_this = today.replace(day=1)
        last_month_end = first_this - datetime.timedelta(days=1)
        start_date = last_month_end.replace(day=1).isoformat()
        end_date = last_month_end.isoformat()
        period_label = f"mês passado ({last_month_end.strftime('%m/%Y')})"
    elif period_lower in ("last_3_months", "ultimos_3_meses", "3_meses") or months_count == 3:
        # 3 meses atrás
        m = today.month - 2
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        start_date = datetime.date(y, m, 1).isoformat()
        end_date = today.isoformat()
        period_label = f"últimos 3 meses (desde {m:02d}/{y})"
    else:
        start_date = (today - datetime.timedelta(days=30)).isoformat()
        end_date = today.isoformat()
        period_label = "últimos 30 dias"

    with get_connection() as conn:
        query = """
            SELECT id, name, category, amount_minor, currency, expense_date, origin, notes
            FROM expenses
            WHERE user_id = ?
              AND expense_date >= ?
              AND expense_date <= ?
        """
        params: List[Any] = [user_id, start_date, end_date]

        if category:
            cat_norm = category.strip().lower()
            if cat_norm in ("restaurante", "restaurantes"):
                query += " AND (LOWER(category) = 'restaurantes' OR LOWER(category) = 'restaurante' OR LOWER(name) LIKE '%restaurante%' OR LOWER(name) LIKE '%almoço%' OR LOWER(name) LIKE '%jantar%')"
            elif cat_norm in ("alimentação", "alimentacao"):
                query += " AND (LOWER(category) = 'alimentação' OR LOWER(category) = 'alimentacao' OR LOWER(name) LIKE '%supermercado%' OR LOWER(name) LIKE '%kero%' OR LOWER(name) LIKE '%jumbo%')"
            elif cat_norm in ("transporte", "transportes"):
                query += " AND (LOWER(category) = 'transporte' OR LOWER(category) = 'transportes' OR LOWER(name) LIKE '%combustível%' OR LOWER(name) LIKE '%combustivel%')"
            else:
                query += " AND (LOWER(category) = ? OR LOWER(category) LIKE ?)"
                params.extend([cat_norm, f"%{cat_norm}%"])

        if min_amount is not None:
            min_minor = int(float(min_amount) * 100)
            query += " AND amount_minor >= ?"
            params.append(min_minor)

        if exclude_savings:
            query += " AND (origin != 'savings' OR origin IS NULL)"

        if order_by == "amount_desc":
            query += " ORDER BY amount_minor DESC, expense_date DESC"
        else:
            query += " ORDER BY expense_date DESC, id DESC"

        if limit is not None and limit > 0:
            query += f" LIMIT {int(limit)}"

        rows = conn.execute(query, params).fetchall()

        total_minor = 0
        consumer_minor = 0
        savings_minor = 0
        discretionary_minor = 0
        essential_minor = 0
        online_minor = 0

        by_category = {}
        by_category_consumer = {}
        by_merchant = {}
        items = []
        online_items = []

        for r in rows:
            amt_minor = r["amount_minor"]
            amt = round(amt_minor / 100.0, 2)
            total_minor += amt_minor
            cat = r["category"] or "Geral"
            origin = r["origin"] or "manual"
            name = r["name"] or "Despesa"

            is_saving = (origin == "savings" or cat.lower() in ("poupança", "poupanca"))
            if is_saving:
                savings_minor += amt_minor
            else:
                consumer_minor += amt_minor
                by_category_consumer[cat] = round(by_category_consumer.get(cat, 0.0) + amt, 2)
                merch_key = name.strip()
                by_merchant[merch_key] = round(by_merchant.get(merch_key, 0.0) + amt, 2)

                cat_clean = cat.strip().lower()
                if any(disc in cat_clean for disc in DISCRETIONARY_CATEGORIES) or "passeio" in name.lower() or "gadgets" in name.lower():
                    discretionary_minor += amt_minor
                else:
                    essential_minor += amt_minor

            by_category[cat] = round(by_category.get(cat, 0.0) + amt, 2)

            # Detetar se é online
            is_online = any(w in name.lower() or w in (r["notes"] or "").lower() for w in ONLINE_KEYWORDS)
            if is_online:
                online_minor += amt_minor
                online_items.append({"name": name, "category": cat, "amount": amt, "date": r["expense_date"]})

            items.append({
                "id": r["id"],
                "name": name,
                "category": cat,
                "amount": amt,
                "date": r["expense_date"],
                "origin": origin,
                "is_savings": is_saving,
                "is_online": is_online,
                "notes": r["notes"] or ""
            })

        sorted_categories = sorted(
            [{"category": k, "total": v} for k, v in by_category.items()],
            key=lambda x: x["total"],
            reverse=True
        )

        sorted_categories_consumer = sorted(
            [{"category": k, "total": v} for k, v in by_category_consumer.items()],
            key=lambda x: x["total"],
            reverse=True
        )

        sorted_merchants = sorted(
            [{"merchant": k, "total": v} for k, v in by_merchant.items()],
            key=lambda x: x["total"],
            reverse=True
        )

        sorted_by_amount = sorted(items, key=lambda x: x["amount"], reverse=True)
        biggest_single = sorted_by_amount[0] if sorted_by_amount else None

        return {
            "period": period,
            "period_label": period_label,
            "start_date": start_date,
            "end_date": end_date,
            "category_filter": category,
            "min_amount_filter": min_amount,
            "total_expenses": round(total_minor / 100.0, 2),
            "consumer_expenses": round(consumer_minor / 100.0, 2),
            "savings_debits": round(savings_minor / 100.0, 2),
            "discretionary_expenses": round(discretionary_minor / 100.0, 2),
            "essential_expenses": round(essential_minor / 100.0, 2),
            "online_expenses": round(online_minor / 100.0, 2),
            "online_items": online_items,
            "currency": "AOA",
            "count": len(items),
            "top_categories": sorted_categories,
            "top_categories_consumer": sorted_categories_consumer,
            "biggest_category": sorted_categories[0] if sorted_categories else None,
            "biggest_consumer_category": sorted_categories_consumer[0] if sorted_categories_consumer else None,
            "biggest_expense": biggest_single,
            "top_merchants": sorted_merchants[:10],
            "top_expenses_ranked": sorted_by_amount[:15],
            "recent_items": items[:15],
            "distinction_note": (
                "Distinção Contabilística BankAO: As saídas de 'Poupança' representam movimentos para metas financeiras "
                "do próprio cliente (acumulação de património), enquanto as restantes categorias representam despesas operacionais de consumo."
            )
        }


def tool_compare_expenses_periods(
    user_id: str,
    period1: str = "setembro",
    period2: str = "outubro"
) -> Dict[str, Any]:
    """
    Compara detalhada e matematicamente as despesas entre dois períodos.
    Exemplo: Setembro vs Outubro, ou Este mês vs Mês passado.
    """
    p1 = tool_get_expenses_analysis(user_id, period=period1)
    p2 = tool_get_expenses_analysis(user_id, period=period2)

    tot1 = p1["total_expenses"]
    tot2 = p2["total_expenses"]
    diff = round(tot2 - tot1, 2)

    pct_change = 0.0
    if tot1 > 0:
        pct_change = round(((tot2 - tot1) / tot1) * 100.0, 1)

    trend = "igual"
    if diff > 0:
        trend = "aumento"
    elif diff < 0:
        trend = "reducao"

    # Comparar apenas consumo (excluindo poupança)
    con1 = p1["consumer_expenses"]
    con2 = p2["consumer_expenses"]
    con_diff = round(con2 - con1, 2)
    con_pct = round(((con2 - con1) / con1) * 100.0, 1) if con1 > 0 else 0.0

    cats1 = {c["category"]: c["total"] for c in p1["top_categories"]}
    cats2 = {c["category"]: c["total"] for c in p2["top_categories"]}
    all_cats = set(cats1.keys()) | set(cats2.keys())

    cat_comparison = []
    for c in all_cats:
        v1 = cats1.get(c, 0.0)
        v2 = cats2.get(c, 0.0)
        c_diff = round(v2 - v1, 2)
        c_pct = round(((v2 - v1) / v1) * 100.0, 1) if v1 > 0 else 100.0 if v2 > 0 else 0.0
        cat_comparison.append({
            "category": c,
            "period1_value": v1,
            "period2_value": v2,
            "difference": c_diff,
            "percent_change": c_pct
        })

    cat_comparison.sort(key=lambda x: abs(x["difference"]), reverse=True)

    return {
        "period1_label": p1["period_label"],
        "period2_label": p2["period_label"],
        "total_period1": tot1,
        "total_period2": tot2,
        "absolute_difference": diff,
        "percent_change": pct_change,
        "trend": trend,
        "consumer_period1": con1,
        "consumer_period2": con2,
        "consumer_difference": con_diff,
        "consumer_percent_change": con_pct,
        "category_comparison": cat_comparison
    }


def tool_get_top_merchants(user_id: str, limit: int = 5, days: int = 365) -> Dict[str, Any]:
    """
    Identifica os comerciantes/estabelecimentos com maiores gastos do cliente.
    """
    limit = min(max(limit, 1), 20)
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT name, category, SUM(amount_minor) as total_minor, COUNT(*) as tx_count,
                   AVG(amount_minor) as avg_minor
            FROM expenses
            WHERE user_id = ? AND expense_date >= ? AND (origin != 'savings' OR origin IS NULL)
            GROUP BY LOWER(TRIM(name))
            ORDER BY total_minor DESC
            LIMIT ?
            """,
            (user_id, cutoff, limit)
        ).fetchall()

        merchants = []
        for r in rows:
            merchants.append({
                "merchant": r["name"],
                "category": r["category"],
                "total": round(r["total_minor"] / 100.0, 2),
                "average_ticket": round(r["avg_minor"] / 100.0, 2),
                "transactions_count": r["tx_count"]
            })

        top_merchant = merchants[0] if merchants else None

        return {
            "days": days,
            "top_merchant": top_merchant,
            "merchants": merchants
        }


def tool_get_recurring_or_duplicate_expenses(user_id: str) -> Dict[str, Any]:
    """
    Identifica despesas repetidas, cobranças regulares e potenciais duplicados na conta.
    """
    with get_connection() as conn:
        # 1. Agrupamento por nome exato e montante semelhante
        rows = conn.execute("""
            SELECT name, category, COUNT(*) as frequency,
                   SUM(amount_minor)/100.0 as total_spent,
                   AVG(amount_minor)/100.0 as avg_amount,
                   MIN(expense_date) as first_seen,
                   MAX(expense_date) as last_seen,
                   origin
            FROM expenses
            WHERE user_id = ?
            GROUP BY LOWER(TRIM(name))
            HAVING frequency > 1
            ORDER BY frequency DESC, total_spent DESC
        """, (user_id,)).fetchall()

        recurring_list = []
        for r in rows:
            is_saving = (r["origin"] == "savings" or r["category"] == "Poupança")
            recurring_list.append({
                "name": r["name"],
                "category": r["category"],
                "frequency": r["frequency"],
                "average_amount": round(r["avg_amount"], 2),
                "total_spent": round(r["total_spent"], 2),
                "first_date": r["first_seen"],
                "last_date": r["last_seen"],
                "is_saving": is_saving,
                "type": "Poupança Programada" if is_saving else "Despesa Fixa Recorrente"
            })

        # 2. Possíveis cobranças duplicadas (mesmo valor e mesmo comerciante num intervalo de 3 dias)
        dup_rows = conn.execute("""
            SELECT e1.name, e1.category, e1.amount_minor/100.0 as amt, e1.expense_date as d1, e2.expense_date as d2
            FROM expenses e1
            JOIN expenses e2 ON e1.user_id = e2.user_id
                            AND e1.id != e2.id
                            AND LOWER(TRIM(e1.name)) = LOWER(TRIM(e2.name))
                            AND e1.amount_minor = e2.amount_minor
                            AND e1.expense_date <= e2.expense_date
                            AND julianday(e2.expense_date) - julianday(e1.expense_date) <= 3
            WHERE e1.user_id = ?
        """, (user_id,)).fetchall()

        duplicates = []
        for d in dup_rows:
            duplicates.append({
                "merchant": d["name"],
                "amount": d["amt"],
                "date_first": d["d1"],
                "date_second": d["d2"]
            })

        return {
            "has_recurring": bool(recurring_list),
            "recurring_count": len(recurring_list),
            "recurring_expenses": recurring_list,
            "has_duplicates": bool(duplicates),
            "potential_duplicates": duplicates,
            "summary": f"Identificadas {len(recurring_list)} cobranças regulares/repetidas e {len(duplicates)} potenciais duplicações."
        }
