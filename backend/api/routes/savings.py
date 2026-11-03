"""
Rotas — Metas de poupança e depósitos nas metas. Tudo vem da base de dados.

Todo o dinheiro que entra numa meta sai da conta do cliente (livro-razão) e fica registado em
Despesas (categoria Poupança). As metas podem ter um dia fixo para o débito automático mensal.
"""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.api.routes.expenses import expense_to_dict
from backend.core.security import get_current_user
from backend.database import get_connection
from backend.database.connection import transaction_scope
from backend.schemas import GoalDepositIn, GoalIn
from backend.services.ledger import InsufficientFundsError, get_account_balance, post_savings_movement
from backend.services.savings import (clamp_day, deposit_into_goal, find_account, next_occurrence,
                                      run_auto_savings)

router = APIRouter(prefix="/api/savings", tags=["Poupança"])


def goal_to_dict(r) -> dict:
    day, start = r["debit_day"], r["start_date"]
    next_debit = None
    if day and start and r["status"] != "completed" and r["monthly_minor"] > 0:
        today = datetime.date.today()
        first = datetime.date.fromisoformat(start)
        # próxima data de débito: a primeira se ainda não chegou, senão a seguinte do mesmo dia
        next_debit = first if first >= today else next_occurrence(day, today - datetime.timedelta(days=1))
        next_debit = next_debit.isoformat()
    return {
        "id": r["id"],
        "name": r["name"],
        "target": r["target_minor"] / 100.0,
        "saved": r["saved_minor"] / 100.0,
        "monthly": r["monthly_minor"] / 100.0,
        "deadline": r["deadline"] or "Indefinido",
        "iconKey": r["icon_key"] or "target",
        "status": r["status"] or "on-track",
        "currency": r["currency"],
        "debitDay": day,
        "startDate": start,
        "nextDebit": next_debit,
    }


def _minor(value: float) -> int:
    return int(round(float(value) * 100))


def _get_goal(conn, goal_id: str, user_id: str):
    row = conn.execute(
        "SELECT * FROM savings_goals WHERE id = ? AND user_id = ?", (goal_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Meta não encontrada.")
    return row


def _resolve_schedule(data: GoalIn, current=None):
    """Valida o débito automático e devolve (debit_day, start_date | None)."""
    start = datetime.date.fromisoformat(data.start_date) if data.start_date else None
    day = data.debit_day or (start.day if start else None)
    if day is None:
        return None, None
    if _minor(data.monthly) <= 0:
        raise HTTPException(status_code=400, detail="Defina o depósito mensal para ativar o débito automático.")
    today = datetime.date.today()
    if start is None:
        keep = current is not None and current["debit_day"] == day and current["start_date"]
        start = datetime.date.fromisoformat(current["start_date"]) if keep else next_occurrence(day, today)
    elif start < today:
        raise HTTPException(status_code=400, detail="A data de início do débito automático não pode estar no passado.")
    if start.day != day:
        start = clamp_day(start.year, start.month, day)
        if start < today:
            start = next_occurrence(day, today)
    return day, start.isoformat()


def _insufficient(exc: InsufficientFundsError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/goals")
def list_goals(current_user: dict = Depends(get_current_user)):
    run_auto_savings(current_user["id"])  # débitos automáticos em atraso
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM savings_goals WHERE user_id = ? ORDER BY created_at DESC, rowid DESC",
            (current_user["id"],),
        ).fetchall()
    return [goal_to_dict(r) for r in rows]


@router.post("/goals", status_code=201)
def create_goal(data: GoalIn, current_user: dict = Depends(get_current_user)):
    goal_id = str(uuid.uuid4())
    day, start = _resolve_schedule(data)
    initial = _minor(data.saved)
    with transaction_scope() as conn:
        conn.execute(
            """
            INSERT INTO savings_goals (id, user_id, name, target_minor, saved_minor, monthly_minor,
                                       deadline, icon_key, status, debit_day, start_date)
            VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
            """,
            (goal_id, current_user["id"], data.name.strip(), _minor(data.target),
             _minor(data.monthly), data.deadline or "Indefinido", data.icon_key, data.status, day, start),
        )
        if initial > 0:
            goal = _get_goal(conn, goal_id, current_user["id"])
            try:  # o saldo inicial também sai da conta
                deposit_into_goal(conn, current_user["id"], goal, initial, datetime.date.today().isoformat(),
                                  "Saldo inicial da meta", f"goal-init:{goal_id}")
            except InsufficientFundsError as exc:
                raise _insufficient(exc)
        row = _get_goal(conn, goal_id, current_user["id"])
    run_auto_savings(current_user["id"])  # se o 1.º débito for hoje, já acontece
    with get_connection() as conn:
        row = _get_goal(conn, goal_id, current_user["id"])
    return goal_to_dict(row)


@router.put("/goals/{goal_id}")
def update_goal(goal_id: str, data: GoalIn, current_user: dict = Depends(get_current_user)):
    with transaction_scope() as conn:
        current = _get_goal(conn, goal_id, current_user["id"])
        # débito automático: se o cliente não enviou dia nem início, desativa
        day, start = _resolve_schedule(data, current)
        target = _minor(data.target)
        status = "completed" if current["saved_minor"] >= target else (
            "on-track" if current["status"] == "completed" and data.status == "completed" else data.status)
        # `saved` não se edita à mão: o dinheiro só entra por depósitos (que debitam a conta)
        conn.execute(
            """
            UPDATE savings_goals SET name = ?, target_minor = ?, monthly_minor = ?, deadline = ?,
                                     icon_key = ?, status = ?, debit_day = ?, start_date = ?
            WHERE id = ? AND user_id = ?
            """,
            (data.name.strip(), target, _minor(data.monthly), data.deadline or "Indefinido",
             data.icon_key, status, day, start, goal_id, current_user["id"]),
        )
        row = _get_goal(conn, goal_id, current_user["id"])
    return goal_to_dict(row)


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: str, current_user: dict = Depends(get_current_user)):
    """Apaga a meta e devolve à conta o que lá estava (anulando as despesas de poupança dessa meta)."""
    refunded = 0
    with transaction_scope() as conn:
        goal = _get_goal(conn, goal_id, current_user["id"])
        if goal["saved_minor"] > 0:
            account = find_account(conn, current_user["id"], goal["currency"])
            post_savings_movement(conn, account["id"], goal["saved_minor"], f"goal-refund:{goal_id}",
                                  f"Resgate da poupança: {goal['name']}", tx_type="savings_refund")
            refunded = goal["saved_minor"]
            conn.execute("DELETE FROM expenses WHERE goal_id = ? AND user_id = ? AND origin = 'savings'",
                         (goal_id, current_user["id"]))
        conn.execute("UPDATE expenses SET goal_id = NULL WHERE goal_id = ? AND user_id = ?", (goal_id, current_user["id"]))
        conn.execute("DELETE FROM savings_goals WHERE id = ? AND user_id = ?", (goal_id, current_user["id"]))
    return {"success": True, "refunded": refunded / 100.0}


@router.post("/goals/{goal_id}/deposit", status_code=201)
def deposit_to_goal(goal_id: str, data: GoalDepositIn, current_user: dict = Depends(get_current_user)):
    """Debita a conta, soma o valor à meta e regista-o nas despesas (categoria Poupança), de forma atómica."""
    day = data.date or datetime.date.today().isoformat()
    amount_minor = _minor(data.amount)
    if amount_minor <= 0:
        raise HTTPException(status_code=400, detail="Indique um valor de depósito válido.")
    key = f"goal-dep:{goal_id}:{data.idempotency_key or uuid.uuid4()}"
    with transaction_scope() as conn:
        goal = _get_goal(conn, goal_id, current_user["id"])
        if conn.execute("SELECT 1 FROM transactions WHERE idempotency_key = ?", (key,)).fetchone():
            raise HTTPException(status_code=409, detail="Este depósito já foi processado.")
        try:
            exp_id = deposit_into_goal(conn, current_user["id"], goal, amount_minor, day,
                                       (data.notes or "").strip() or "Depósito manual (fora do débito automático)", key)
        except InsufficientFundsError as exc:
            raise _insufficient(exc)
        goal = _get_goal(conn, goal_id, current_user["id"])
        expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (exp_id,)).fetchone()
        account = find_account(conn, current_user["id"], goal["currency"])
        balance = get_account_balance(account["id"], conn) / 100.0
    return {"goal": goal_to_dict(goal), "expense": expense_to_dict(expense), "balance": balance}
