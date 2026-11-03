"""
Rotas — Despesas e metas habituais (orçamento) por categoria. Tudo vem da base de dados.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.core.security import get_current_user
from backend.database import get_connection
from backend.database.connection import transaction_scope
from backend.schemas import BudgetIn, ExpenseIn
from backend.schemas.finance import CATEGORIAS

router = APIRouter(prefix="/api", tags=["Despesas"])


def expense_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "category": r["category"],
        "amount": r["amount_minor"] / 100.0,
        "currency": r["currency"],
        "date": r["expense_date"],
        "origin": r["origin"],
        "notes": r["notes"] or "",
        "goalId": r["goal_id"],
    }


def _minor(value: float) -> int:
    return int(round(float(value) * 100))


@router.get("/expenses")
def list_expenses(current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY expense_date DESC, created_at DESC, rowid DESC",
            (current_user["id"],),
        ).fetchall()
    return [expense_to_dict(r) for r in rows]


@router.post("/expenses", status_code=201)
def create_expense(data: ExpenseIn, current_user: dict = Depends(get_current_user)):
    exp_id = str(uuid.uuid4())
    with transaction_scope() as conn:
        conn.execute(
            """
            INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (exp_id, current_user["id"], data.name.strip(), data.category, _minor(data.amount),
             data.currency.upper(), data.date, data.origin, (data.notes or "").strip()),
        )
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (exp_id,)).fetchone()
    return expense_to_dict(row)


@router.put("/expenses/{expense_id}")
def update_expense(expense_id: str, data: ExpenseIn, current_user: dict = Depends(get_current_user)):
    with transaction_scope() as conn:
        old = conn.execute(
            "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, current_user["id"])
        ).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Despesa não encontrada.")
        new_minor = _minor(data.amount)
        conn.execute(
            """
            UPDATE expenses SET name = ?, category = ?, amount_minor = ?, expense_date = ?, notes = ?
            WHERE id = ? AND user_id = ?
            """,
            (data.name.strip(), data.category, new_minor, data.date, (data.notes or "").strip(),
             expense_id, current_user["id"]),
        )
        # Depósito numa meta: a meta acompanha a diferença de valor
        if old["goal_id"] and new_minor != old["amount_minor"]:
            conn.execute(
                "UPDATE savings_goals SET saved_minor = MAX(0, saved_minor + ?) WHERE id = ? AND user_id = ?",
                (new_minor - old["amount_minor"], old["goal_id"], current_user["id"]),
            )
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    return expense_to_dict(row)


@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: str, current_user: dict = Depends(get_current_user)):
    with transaction_scope() as conn:
        old = conn.execute(
            "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, current_user["id"])
        ).fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Despesa não encontrada.")
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        if old["goal_id"]:
            conn.execute(
                "UPDATE savings_goals SET saved_minor = MAX(0, saved_minor - ?) WHERE id = ? AND user_id = ?",
                (old["amount_minor"], old["goal_id"], current_user["id"]),
            )
    return {"success": True}


# ---------- Metas habituais por categoria ----------

@router.get("/budgets")
def list_budgets(current_user: dict = Depends(get_current_user)):
    """Só devolve as categorias a que o utilizador definiu uma meta."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, amount_minor FROM category_budgets WHERE user_id = ?", (current_user["id"],)
        ).fetchall()
    return {r["category"]: r["amount_minor"] / 100.0 for r in rows}


@router.put("/budgets/{category}")
def set_budget(category: str, data: BudgetIn, current_user: dict = Depends(get_current_user)):
    if category not in CATEGORIAS:
        raise HTTPException(status_code=400, detail="Categoria inválida.")
    with transaction_scope() as conn:
        conn.execute(
            """
            INSERT INTO category_budgets (user_id, category, amount_minor) VALUES (?, ?, ?)
            ON CONFLICT(user_id, category) DO UPDATE SET amount_minor = excluded.amount_minor,
                                                         updated_at = CURRENT_TIMESTAMP
            """,
            (current_user["id"], category, _minor(data.amount)),
        )
    return {"category": category, "amount": _minor(data.amount) / 100.0}
