"""
Rotas — Analítica de conta: GET /api/accounts/analytics

Tudo é derivado de dados reais (`ledger_entries`, `transactions`, `transfers`,
`expenses` e `savings_goals`); não há valores fictícios.

Notas de agregação (sem `account_id`):
  Agrega todas as contas do utilizador. Quando há moedas mistas, os valores em
  `summary`/`in_out_series` são somados em minor units SEM conversão cambial e
  rotulados com a moeda da conta principal (a conta AOA, se existir; senão a
  primeira conta). `per_account` mantém sempre a moeda própria de cada conta.

Regras de classificação (`by_kind` em `per_account`):
  - compras: saídas `transfer_iban` do ledger + despesas (`expenses`) do período.
    Como `expenses` não tem conta, as despesas são atribuídas à conta de mesma
    moeda (ou à principal, se só houver uma moeda selecionada).
  - levantamentos: saídas `transfer_internal` do ledger.
  - estornos: créditos que revertem — tipo em {reversal, estorno, refund,
    savings_refund} OU qualquer crédito que não seja depósito, receção interna
    nem câmbio de entrada (regra documentada aqui).
  - pendentes: soma (absoluta) de depósitos `pending`, transferências `pending`
    e lançamentos de transações `pending` ligados à conta.
"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.security import get_current_user
from backend.database import get_connection

router = APIRouter(prefix="/api/accounts", tags=["Analítica"])

REVERSAL_TYPES = {"reversal", "estorno", "refund", "savings_refund", "chargeback"}
KNOWN_CREDIT_TYPES = {"deposit", "transfer_internal", "fx_exchange"}


def _dec(minor: int) -> float:
    return round(int(minor) / 100.0, 2)


def _period_key(d: datetime.date, unit: str) -> str:
    if unit == "day":
        return d.isoformat()
    if unit == "week":
        return (d - datetime.timedelta(days=d.weekday())).isoformat()
    if unit == "month":
        return f"{d.year:04d}-{d.month:02d}"
    return f"{d.year:04d}"


def _period_keys(start: datetime.date, end: datetime.date, unit: str):
    keys, seen = [], set()
    cur = start
    while cur <= end:
        k = _period_key(cur, unit)
        if k not in seen:
            seen.add(k)
            keys.append(k)
        cur += datetime.timedelta(days=1)
    return keys


def _parse_date(value) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _kind(tx_type: str, amount_minor: int) -> str:
    credit = amount_minor > 0
    if tx_type == "deposit":
        return "deposito"
    if tx_type == "transfer_internal":
        return "rececao_interna" if credit else "levantamento"
    if tx_type == "transfer_iban":
        return "iban"
    if tx_type == "fx_exchange":
        return "cambio_entrada" if credit else "cambio_saida"
    if tx_type in ("savings_deposit", "savings"):
        return "poupanca"
    if tx_type in REVERSAL_TYPES or (credit and tx_type not in KNOWN_CREDIT_TYPES):
        return "estorno"
    return tx_type or "outro"


def _is_estorno(tx_type: str, amount_minor: int) -> bool:
    return amount_minor > 0 and (
        tx_type in REVERSAL_TYPES or tx_type not in KNOWN_CREDIT_TYPES
    )


@router.get("/analytics")
def get_account_analytics(
    account_id: Optional[str] = Query(default=None),
    range_days: int = Query(default=30),
    granularity: str = Query(default="day"),
    period_unit: str = Query(default="month"),
    projection_days: int = Query(default=90, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    if range_days not in (7, 30, 90, 180, 365):
        raise HTTPException(status_code=422, detail="range_days deve ser 7, 30, 90, 180 ou 365.")
    if granularity not in ("day", "week", "month"):
        raise HTTPException(status_code=422, detail="granularity deve ser day, week ou month.")
    if period_unit not in ("week", "month", "year"):
        raise HTTPException(status_code=422, detail="period_unit deve ser week, month ou year.")
    user_id = current_user["id"]
    today = datetime.date.today()
    end = today
    start = today - datetime.timedelta(days=range_days - 1)

    with get_connection() as conn:
        accounts = conn.execute(
            "SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at ASC, id ASC",
            (user_id,),
        ).fetchall()

        if account_id:
            match = [a for a in accounts if a["id"] == account_id]
            if not match:
                exists = conn.execute(
                    "SELECT id FROM accounts WHERE id = ?", (account_id,)
                ).fetchone()
                if exists:
                    raise HTTPException(status_code=403, detail="Conta pertence a outro utilizador.")
                raise HTTPException(status_code=404, detail="Conta não encontrada.")
            selected = match
        else:
            selected = accounts

        account_ids = [a["id"] for a in selected]
        primary = next((a for a in selected if a["currency"] == "AOA"), selected[0] if selected else None)
        currency = primary["currency"] if primary else "AOA"

        entries, expenses, transfers = [], [], []
        pending_by_account = {aid: 0 for aid in account_ids}
        current_balance = 0
        if account_ids:
            ph = ",".join("?" for _ in account_ids)
            entries = conn.execute(
                f"""
                SELECT l.id, l.transaction_id, l.account_id, l.amount_minor, l.currency,
                       l.created_at, t.type, t.status, t.description,
                       a.account_number
                FROM ledger_entries l
                JOIN transactions t ON t.id = l.transaction_id
                JOIN accounts a ON a.id = l.account_id
                WHERE l.account_id IN ({ph}) AND date(l.created_at) >= ? AND date(l.created_at) <= ?
                ORDER BY date(l.created_at) ASC, l.id ASC
                """,
                (*account_ids, start.isoformat(), end.isoformat()),
            ).fetchall()
            row = conn.execute(
                f"SELECT COALESCE(SUM(amount_minor),0) AS b FROM ledger_entries WHERE account_id IN ({ph})",
                account_ids,
            ).fetchone()
            current_balance = int(row["b"])

            expenses = conn.execute(
                "SELECT * FROM expenses WHERE user_id = ? AND expense_date >= ? AND expense_date <= ? ORDER BY expense_date ASC",
                (user_id, start.isoformat(), end.isoformat()),
            ).fetchall()
            transfers = conn.execute(
                f"""
                SELECT tr.* FROM transfers tr
                WHERE tr.from_account_id IN ({ph}) AND date(tr.created_at) >= ? AND date(tr.created_at) <= ?
                """,
                (*account_ids, start.isoformat(), end.isoformat()),
            ).fetchall()
            # Pendentes: depósitos/transferências pending + lançamentos pending (sem duplicar).
            seen_tx = set()
            dep_rows = conn.execute(
                f"SELECT transaction_id, account_id, amount_minor FROM deposits WHERE account_id IN ({ph}) AND status='pending'",
                account_ids,
            ).fetchall()
            for r in dep_rows:
                pending_by_account[r["account_id"]] += abs(int(r["amount_minor"]))
                seen_tx.add(r["transaction_id"])
            tr_rows = conn.execute(
                f"SELECT transaction_id, from_account_id, source_amount_minor FROM transfers WHERE from_account_id IN ({ph}) AND status='pending'",
                account_ids,
            ).fetchall()
            for r in tr_rows:
                pending_by_account[r["from_account_id"]] += abs(int(r["source_amount_minor"]))
                seen_tx.add(r["transaction_id"])
            led_rows = conn.execute(
                f"""
                SELECT l.account_id, l.amount_minor, l.transaction_id FROM ledger_entries l
                JOIN transactions t ON t.id = l.transaction_id
                WHERE l.account_id IN ({ph}) AND t.status='pending'
                """,
                account_ids,
            ).fetchall()
            for r in led_rows:
                if r["transaction_id"] not in seen_tx:
                    pending_by_account[r["account_id"]] += abs(int(r["amount_minor"]))

        # ---- summary & balance_series ----
        total_in = sum(int(e["amount_minor"]) for e in entries if e["amount_minor"] > 0)
        total_out = -sum(int(e["amount_minor"]) for e in entries if e["amount_minor"] < 0)
        period_net = total_in - total_out
        initial_balance = current_balance - period_net

        daily = {}
        for e in entries:
            d = _parse_date(e["created_at"])
            if d:
                daily[d] = daily.get(d, 0) + int(e["amount_minor"])

        balance_series, balances = [], [initial_balance]
        if entries:
            bal = initial_balance
            cur = start
            while cur <= end:
                bal += daily.get(cur, 0)
                balances.append(bal)
                balance_series.append({"date": cur.isoformat(), "balance": _dec(bal), "balance_minor": bal})
                cur += datetime.timedelta(days=1)

        summary = {
            "initial_balance": _dec(initial_balance), "initial_balance_minor": initial_balance,
            "current_balance": _dec(current_balance), "current_balance_minor": current_balance,
            "max_balance": _dec(max(balances)), "max_balance_minor": max(balances),
            "min_balance": _dec(min(balances)), "min_balance_minor": min(balances),
            "total_in": _dec(total_in), "total_in_minor": total_in,
            "total_out": _dec(total_out), "total_out_minor": total_out,
            "net": _dec(period_net), "net_minor": period_net,
            "currency": currency,
        }

        # ---- in_out_series (granularity + by_week/by_month/by_year + period_unit) ----
        def grouped(unit, fill=False):
            agg = {}
            for e in entries:
                d = _parse_date(e["created_at"])
                if not d:
                    continue
                slot = agg.setdefault(_period_key(d, unit), {"in": 0, "out": 0})
                amt = int(e["amount_minor"])
                if amt > 0:
                    slot["in"] += amt
                else:
                    slot["out"] += -amt
            keys = _period_keys(start, end, unit) if fill else sorted(agg)
            return [
                {"period": k, "in": _dec(agg.get(k, {}).get("in", 0)), "in_minor": agg.get(k, {}).get("in", 0),
                 "out": _dec(agg.get(k, {}).get("out", 0)), "out_minor": agg.get(k, {}).get("out", 0),
                 "net": _dec(agg.get(k, {}).get("in", 0) - agg.get(k, {}).get("out", 0)),
                 "net_minor": agg.get(k, {}).get("in", 0) - agg.get(k, {}).get("out", 0)}
                for k in keys
            ]

        in_out_series = grouped(granularity, fill=bool(entries))

        # ---- per_account ----
        expense_by_account = {aid: 0 for aid in account_ids}
        for exp in expenses:
            target = next((a for a in selected if a["currency"] == exp["currency"]), primary)
            if target:
                expense_by_account[target["id"]] += int(exp["amount_minor"])
        per_account = []
        for a in selected:
            acc_entries = [e for e in entries if e["account_id"] == a["id"]]
            compras = -sum(int(e["amount_minor"]) for e in acc_entries
                           if e["amount_minor"] < 0 and e["type"] == "transfer_iban") + expense_by_account[a["id"]]
            levantamentos = -sum(int(e["amount_minor"]) for e in acc_entries
                                 if e["amount_minor"] < 0 and e["type"] == "transfer_internal")
            estornos = sum(int(e["amount_minor"]) for e in acc_entries if _is_estorno(e["type"], int(e["amount_minor"])))
            acc_out = -sum(int(e["amount_minor"]) for e in acc_entries if e["amount_minor"] < 0)
            by_kind_minor = {"compras": compras, "levantamentos": levantamentos,
                             "estornos": estornos, "pendentes": pending_by_account[a["id"]]}
            per_account.append({
                "account_id": a["id"], "account_number": a["account_number"], "currency": a["currency"],
                "total_out": _dec(acc_out), "total_out_minor": acc_out,
                "by_kind": {k: _dec(v) for k, v in by_kind_minor.items()},
                "by_kind_minor": by_kind_minor,
            })

        # ---- operations (últimas 100) ----
        operations = [
            {"id": e["id"], "transaction_id": e["transaction_id"],
             "date": str(e["created_at"])[:10], "created_at": e["created_at"],
             "description": e["description"] or "", "type": e["type"], "status": e["status"],
             "amount": _dec(int(e["amount_minor"])), "amount_minor": int(e["amount_minor"]),
             "currency": e["currency"], "kind": _kind(e["type"], int(e["amount_minor"])),
             "account_id": e["account_id"]}
            for e in sorted(entries, key=lambda x: (str(x["created_at"]), x["id"]), reverse=True)[:100]
        ]

        # ---- merchants (top 10) ----
        merch = {}
        for t in transfers:
            if t["status"] == "failed":
                continue
            name = (t["beneficiary_name"] or "").strip()
            if name:
                m = merch.setdefault(name, {"total": 0, "count": 0})
                m["total"] += int(t["source_amount_minor"]); m["count"] += 1
        for exp in expenses:
            name = (exp["name"] or "").strip()
            if name:
                m = merch.setdefault(name, {"total": 0, "count": 0})
                m["total"] += int(exp["amount_minor"]); m["count"] += 1
        merchants = [
            {"name": n, "total": _dec(v["total"]), "total_minor": v["total"], "count": v["count"]}
            for n, v in sorted(merch.items(), key=lambda kv: (-kv[1]["total"], kv[0]))[:10]
        ]

        # ---- flow (Sankey) ----
        origins = {"depositos": 0, "rececao_interna": 0, "cambio_entrada": 0}
        dests = {"transferencias_internas": 0, "iban": 0, "cambio_saida": 0, "despesas": 0, "poupancas": 0}
        for e in entries:
            amt, t = int(e["amount_minor"]), e["type"]
            if amt > 0 and t == "deposit":
                origins["depositos"] += amt
            elif amt > 0 and t == "transfer_internal":
                origins["rececao_interna"] += amt
            elif amt > 0 and t == "fx_exchange":
                origins["cambio_entrada"] += amt
            elif amt < 0 and t == "transfer_internal":
                dests["transferencias_internas"] += -amt
            elif amt < 0 and t == "transfer_iban":
                dests["iban"] += -amt
            elif amt < 0 and t == "fx_exchange":
                dests["cambio_saida"] += -amt
            elif amt < 0 and t in ("savings_deposit", "savings"):
                dests["poupancas"] += -amt
        dests["despesas"] = sum(int(x["amount_minor"]) for x in expenses)
        labels = {"depositos": "Depósitos", "rececao_interna": "Receção interna", "cambio_entrada": "Câmbio entrada",
                  "conta": "Conta", "transferencias_internas": "Transferências internas", "iban": "IBAN",
                  "cambio_saida": "Câmbio saída", "despesas": "Despesas", "poupancas": "Poupanças"}
        links = ([{"source": k, "target": "conta", "value": _dec(v), "value_minor": v, "kind": k}
                  for k, v in origins.items() if v > 0]
                 + [{"source": "conta", "target": k, "value": _dec(v), "value_minor": v, "kind": k}
                    for k, v in dests.items() if v > 0])
        node_ids = {l["source"] for l in links} | {l["target"] for l in links}
        flow = {"nodes": [{"id": n, "label": labels[n]} for n in labels if n in node_ids], "links": links}

        # ---- projection (estimativa, últimos 90 dias) ----
        proj_start = today - datetime.timedelta(days=89)
        inc90 = exp90 = 0
        if account_ids:
            ph = ",".join("?" for _ in account_ids)
            rows90 = conn.execute(
                    f"""SELECT l.amount_minor, t.type FROM ledger_entries l JOIN transactions t ON t.id=l.transaction_id
                        WHERE l.account_id IN ({ph}) AND date(l.created_at) >= ? AND date(l.created_at) <= ?""",
                    (*account_ids, proj_start.isoformat(), today.isoformat()),
                ).fetchall()
            for r in rows90:
                amt = int(r["amount_minor"])
                if amt > 0:
                    inc90 += amt
                elif r["type"] not in ("savings_deposit", "savings"):
                    exp90 += -amt
        monthly_income = int(round(inc90 * 30 / 90))
        monthly_expense = int(round(exp90 * 30 / 90))
        savings_row = conn.execute(
            "SELECT COALESCE(SUM(monthly_minor),0) AS s FROM savings_goals WHERE user_id=? AND status!='completed'",
            (user_id,),
        ).fetchone()
        scheduled_savings = int(savings_row["s"])

    daily_net = (monthly_income - monthly_expense - scheduled_savings) / 30.0
    threshold = current_balance * 0.10
    points, alerts = [], []
    bal = float(current_balance)
    prev = float(current_balance)
    for i in range(1, projection_days + 1):
        bal += daily_net
        d = today + datetime.timedelta(days=i)
        b = int(round(bal))
        points.append({"date": d.isoformat(), "balance": _dec(b), "balance_minor": b, "projected": True})
        if prev >= threshold and b < threshold or (b < 0 and prev >= 0):
            alerts.append({"date": d.isoformat(), "balance": _dec(b), "balance_minor": b})
        prev = b

    return {
        "account_id": account_id,
        "currency": currency,
        "range_days": range_days,
        "granularity": granularity,
        "period_unit": period_unit,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "aggregation_note": "Sem account_id agrega todas as contas; com moedas mistas soma minor units sem conversão, rotulado com a moeda da conta principal (AOA se existir).",
        "summary": summary,
        "balance_series": balance_series,
        "in_out_series": in_out_series,
        "comparison_series": grouped(period_unit) if account_ids else [],
        "by_week": grouped("week") if account_ids else [],
        "by_month": grouped("month") if account_ids else [],
        "by_year": grouped("year") if account_ids else [],
        "per_account": per_account,
        "operations": operations,
        "merchants": merchants,
        "flow": flow,
        "projection": {
            "points": points,
            "assumptions": {
                "monthly_income_estimate": _dec(monthly_income), "monthly_income_estimate_minor": monthly_income,
                "monthly_expense_estimate": _dec(monthly_expense), "monthly_expense_estimate_minor": monthly_expense,
                "scheduled_savings_monthly": _dec(scheduled_savings), "scheduled_savings_monthly_minor": scheduled_savings,
                "lookback_days": 90, "projection_days": projection_days,
            },
            "low_balance_alerts": alerts,
            "is_estimate": True,
        },
    }
