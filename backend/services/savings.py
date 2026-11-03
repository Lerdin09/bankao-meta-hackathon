"""
Poupança — lógica partilhada: depósito numa meta (debita a conta + regista a despesa) e
débito automático mensal num dia escolhido pelo cliente.

Regras:
  • Todo o dinheiro que entra numa meta SAI da conta (livro-razão) e fica registado em Despesas
    (categoria Poupança), de forma atómica.
  • O débito automático corre no dia escolhido; se o saldo faltar, tenta de novo nas execuções
    seguintes e nunca debita duas vezes o mesmo mês (chave de idempotência por meta + mês).
"""
import calendar
import datetime
import logging
import uuid
from typing import Optional

from backend.database import get_connection
from backend.database.connection import transaction_scope
from backend.services.ledger import InsufficientFundsError, post_savings_movement

logger = logging.getLogger("bankao.savings")


def clamp_day(year: int, month: int, day: int) -> datetime.date:
    """Dia 31 num mês de 30 dias (ou 29/30 em fevereiro) cai no último dia do mês."""
    return datetime.date(year, month, min(day, calendar.monthrange(year, month)[1]))


def next_occurrence(day: int, after: datetime.date) -> datetime.date:
    """Próxima data com esse dia do mês, estritamente depois de `after`."""
    d = clamp_day(after.year, after.month, day)
    if d > after:
        return d
    y, m = (after.year + 1, 1) if after.month == 12 else (after.year, after.month + 1)
    return clamp_day(y, m, day)


def find_account(conn, user_id: str, currency: str):
    row = conn.execute(
        "SELECT id, currency FROM accounts WHERE user_id = ? AND currency = ? AND status = 'active' LIMIT 1",
        (user_id, currency),
    ).fetchone()
    if not row:
        raise ValueError(f"Não existe conta ativa em {currency} para debitar.")
    return row


def deposit_into_goal(conn, user_id: str, goal, amount_minor: int, day: str, notes: str,
                      idem_key: str, origin: str = "savings", label: str = "Depósito na poupança"):
    """
    Debita a conta, soma à meta e regista a despesa. Corre dentro da transação do chamador.
    Lança InsufficientFundsError se o saldo não chegar.
    """
    account = find_account(conn, user_id, goal["currency"])
    post_savings_movement(conn, account["id"], -amount_minor, idem_key, f"{label}: {goal['name']}")
    new_saved = goal["saved_minor"] + amount_minor
    status = "completed" if new_saved >= goal["target_minor"] else goal["status"]
    conn.execute("UPDATE savings_goals SET saved_minor = ?, status = ? WHERE id = ? AND user_id = ?",
                 (new_saved, status, goal["id"], user_id))
    exp_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, notes, goal_id)
        VALUES (?, ?, ?, 'Poupança', ?, ?, ?, ?, ?, ?)
        """,
        (exp_id, user_id, f"{label}: {goal['name']}", amount_minor, goal["currency"], day, origin, notes, goal["id"]),
    )
    return exp_id


def run_auto_savings(user_id: Optional[str] = None, today: Optional[datetime.date] = None) -> int:
    """
    Executa os débitos automáticos em atraso (de todos os utilizadores ou de um só).
    Devolve quantos débitos foram feitos. Seguro para chamar várias vezes.
    """
    today = today or datetime.date.today()
    query = ("SELECT * FROM savings_goals WHERE debit_day IS NOT NULL AND start_date IS NOT NULL "
             "AND monthly_minor > 0 AND status != 'completed'")
    params: tuple = ()
    if user_id:
        query += " AND user_id = ?"
        params = (user_id,)
    with get_connection() as conn:
        goals = conn.execute(query, params).fetchall()

    done = 0
    for g in goals:
        try:
            start = datetime.date.fromisoformat(g["start_date"])
        except ValueError:
            continue
        y, m = start.year, start.month
        for _ in range(240):
            if (y, m) > (today.year, today.month):
                break
            due = clamp_day(y, m, g["debit_day"])
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            if due < start:
                continue
            if due > today:
                break
            key = f"auto:{g['id']}:{due.year}-{due.month:02d}"
            try:
                with transaction_scope() as conn:
                    goal = conn.execute("SELECT * FROM savings_goals WHERE id = ?", (g["id"],)).fetchone()
                    if not goal or goal["status"] == "completed":
                        break
                    if conn.execute("SELECT 1 FROM transactions WHERE idempotency_key = ?", (key,)).fetchone():
                        continue
                    remaining = goal["target_minor"] - goal["saved_minor"]
                    if remaining <= 0:
                        break
                    amount = min(goal["monthly_minor"], remaining)
                    deposit_into_goal(
                        conn, goal["user_id"], goal, amount, due.isoformat(),
                        f"Débito automático no dia {g['debit_day']}", key,
                        origin="savings", label="Poupança automática",
                    )
                    done += 1
            except InsufficientFundsError:
                logger.info("Saldo insuficiente para o débito automático da meta %s (%s).", g["id"], key)
                break  # volta a tentar na próxima execução, mantendo a ordem dos meses
            except Exception:
                logger.exception("Falha no débito automático da meta %s", g["id"])
                break
    return done
