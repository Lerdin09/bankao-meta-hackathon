"""
Ferramentas de Contas e Saldos para a IA do BankAO.
Consulta o livro-razão (double-entry ledger) real e contas ativas.
"""
import datetime
from typing import Any, Dict, List, Optional

from backend.database import get_connection
from backend.services.ledger import get_user_accounts as fetch_accounts


def tool_get_accounts(user_id: str) -> Dict[str, Any]:
    """
    Consulta todas as contas e saldos em tempo real do utilizador autenticado.
    Retorna contas em AOA, EUR, USD com saldo disponível e contabilístico.
    """
    accounts = fetch_accounts(user_id)
    total_aoa = 0.0
    currencies_breakdown = {}

    for acc in accounts:
        cur = acc["currency"]
        bal = acc["balance_decimal"]
        currencies_breakdown[cur] = bal
        if cur == "AOA":
            total_aoa += bal

    return {
        "accounts_count": len(accounts),
        "accounts": [
            {
                "id": a["id"],
                "account_number": a["account_number"],
                "iban": a["iban_virtual"],
                "currency": a["currency"],
                "balance": a["balance_decimal"],
                "status": a["status"]
            }
            for a in accounts
        ],
        "total_aoa": round(total_aoa, 2),
        "currencies": currencies_breakdown
    }


def tool_get_statement(
    user_id: str,
    account_id: Optional[str] = None,
    days: int = 30,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Consulta os movimentos reais da conta no período especificado.
    """
    days = min(max(days, 1), 365)
    limit = min(max(limit, 1), 50)
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    with get_connection() as conn:
        user_accounts = conn.execute(
            "SELECT id, account_number, currency FROM accounts WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        acc_map = {a["id"]: a for a in user_accounts}

        if account_id and account_id not in acc_map:
            return {"error": "Conta não encontrada ou não pertence ao utilizador.", "movements": []}

        filter_accs = [account_id] if account_id else list(acc_map.keys())
        if not filter_accs:
            return {"movements": [], "total_entries": 0}

        ph = ",".join("?" for _ in filter_accs)
        params = list(filter_accs) + [cutoff, limit]

        query = f"""
            SELECT l.id, l.transaction_id, l.account_id, l.amount_minor, l.currency,
                   l.created_at, t.type as tx_type, t.description, t.status
            FROM ledger_entries l
            JOIN transactions t ON t.id = l.transaction_id
            WHERE l.account_id IN ({ph})
              AND l.created_at >= ?
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT ?
        """
        rows = conn.execute(query, params).fetchall()

        movements = []
        for r in rows:
            amt = round(r["amount_minor"] / 100.0, 2)
            direction = "entrada" if amt > 0 else "saida"
            movements.append({
                "date": str(r["created_at"])[:19],
                "description": r["description"] or r["tx_type"],
                "amount": abs(amt),
                "direction": direction,
                "currency": r["currency"],
                "tx_type": r["tx_type"],
                "status": r["status"]
            })

        return {
            "period_days": days,
            "movements_count": len(movements),
            "movements": movements
        }


def tool_get_incomes(user_id: str, period: str = "this_month") -> Dict[str, Any]:
    """
    Calcula as receitas recebidas (créditos no ledger: depósitos, transferências recebidas, etc.)
    no período solicitado ('this_month', 'last_month', 'last_7_days', 'last_30_days').
    """
    today = datetime.date.today()
    if period == "this_month":
        start_date = today.replace(day=1).isoformat()
        end_date = today.isoformat() + " 23:59:59"
        period_label = f"este mês ({today.strftime('%m/%Y')})"
    elif period == "last_month":
        first_this = today.replace(day=1)
        last_month_end = first_this - datetime.timedelta(days=1)
        start_date = last_month_end.replace(day=1).isoformat()
        end_date = last_month_end.isoformat() + " 23:59:59"
        period_label = f"mês passado ({last_month_end.strftime('%m/%Y')})"
    elif period == "last_7_days":
        start_date = (today - datetime.timedelta(days=7)).isoformat()
        end_date = today.isoformat() + " 23:59:59"
        period_label = "últimos 7 dias"
    else:
        start_date = (today - datetime.timedelta(days=30)).isoformat()
        end_date = today.isoformat() + " 23:59:59"
        period_label = "últimos 30 dias"

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT l.amount_minor, l.currency, l.created_at, t.type as tx_type, t.description
            FROM ledger_entries l
            JOIN accounts a ON a.id = l.account_id
            JOIN transactions t ON t.id = l.transaction_id
            WHERE a.user_id = ?
              AND l.amount_minor > 0
              AND l.created_at >= ?
              AND l.created_at <= ?
            ORDER BY l.created_at DESC
            """,
            (user_id, start_date, end_date)
        ).fetchall()

        total_by_currency = {}
        entries = []
        for r in rows:
            cur = r["currency"]
            amt = round(r["amount_minor"] / 100.0, 2)
            total_by_currency[cur] = round(total_by_currency.get(cur, 0.0) + amt, 2)
            entries.append({
                "date": str(r["created_at"])[:10],
                "description": r["description"] or r["tx_type"],
                "amount": amt,
                "currency": cur,
                "type": r["tx_type"]
            })

        return {
            "period": period,
            "period_label": period_label,
            "total_by_currency": total_by_currency,
            "total_aoa": total_by_currency.get("AOA", 0.0),
            "entries_count": len(entries),
            "entries": entries[:10]
        }
