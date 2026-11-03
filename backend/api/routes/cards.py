"""
Rotas — Módulo de Cartões Bancários (físicos e virtuais).
Gestão de cartões, controlos de segurança, limites, movimentos,
despesas por categoria, notificações e cartões virtuais.
"""
import datetime
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.security import get_current_user
from backend.database import get_connection

router = APIRouter(prefix="/api/cards", tags=["Cartões"])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_minor(v: float) -> int:
    return int(round(float(v) * 100))

def _to_decimal(m: int) -> float:
    return round(float(m) / 100.0, 2)

def _today() -> str:
    return datetime.date.today().isoformat()

def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CardControlIn(BaseModel):
    action: str  # 'block', 'unblock', 'cancel'
    reason: Optional[str] = None

class CardSettingsIn(BaseModel):
    online_payments: Optional[bool] = None
    international_payments: Optional[bool] = None
    atm_withdrawals: Optional[bool] = None
    contactless: Optional[bool] = None
    daily_limit_minor: Optional[int] = None
    monthly_limit_minor: Optional[int] = None

class VirtualCardIn(BaseModel):
    account_id: str
    label: Optional[str] = "Cartão Virtual"
    single_use: bool = False
    spending_limit_minor: Optional[int] = None
    expires_in_days: int = 365

class NotifReadIn(BaseModel):
    notification_id: str


# ─── Helpers de DB ────────────────────────────────────────────────────────────

def _get_card(conn, card_id: str, user_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM cards WHERE id = ? AND user_id = ?",
        (card_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cartão não encontrado.")
    return dict(row)


def _format_card(row: dict) -> dict:
    """Formata um row de cartão para a API."""
    daily_spent = _to_decimal(row.get("daily_spent_minor") or 0)
    monthly_spent = _to_decimal(row.get("monthly_spent_minor") or 0)
    daily_limit = _to_decimal(row.get("daily_limit_minor") or 0)
    monthly_limit = _to_decimal(row.get("monthly_limit_minor") or 0)
    credit_limit = _to_decimal(row.get("credit_limit_minor") or 0)
    credit_used = _to_decimal(row.get("credit_used_minor") or 0)

    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "user_id": row["user_id"],
        "card_type": row["card_type"],           # 'debit', 'credit', 'virtual'
        "network": row["network"],               # 'visa', 'mastercard', 'multicaixa'
        "last_four": row["last_four"],
        "cardholder_name": row["cardholder_name"],
        "expires_month": row["expires_month"],
        "expires_year": row["expires_year"],
        "status": row["status"],                 # 'active', 'blocked', 'cancelled'
        "is_virtual": bool(row.get("is_virtual")),
        "is_single_use": bool(row.get("is_single_use")),
        "label": row.get("label") or "",
        "color_scheme": row.get("color_scheme") or "blue",
        "online_payments": bool(row.get("online_payments", 1)),
        "international_payments": bool(row.get("international_payments", 1)),
        "atm_withdrawals": bool(row.get("atm_withdrawals", 1)),
        "contactless": bool(row.get("contactless", 1)),
        "daily_limit": daily_limit,
        "daily_limit_minor": row.get("daily_limit_minor") or 0,
        "monthly_limit": monthly_limit,
        "monthly_limit_minor": row.get("monthly_limit_minor") or 0,
        "daily_spent": daily_spent,
        "monthly_spent": monthly_spent,
        "credit_limit": credit_limit,
        "credit_used": credit_used,
        "credit_available": round(credit_limit - credit_used, 2),
        "currency": row.get("currency") or "AOA",
        "institution": row.get("institution") or "BankAO",
        "created_at": row.get("created_at"),
    }


def _format_movement(row: dict) -> dict:
    return {
        "id": row["id"],
        "card_id": row["card_id"],
        "amount": _to_decimal(row.get("amount_minor") or 0),
        "currency": row.get("currency") or "AOA",
        "merchant_name": row.get("merchant_name") or "—",
        "merchant_category": row.get("merchant_category") or "outros",
        "merchant_logo": row.get("merchant_logo"),
        "operation_type": row.get("operation_type") or "compra",
        "status": row.get("status") or "completed",
        "description": row.get("description") or "",
        "created_at": row.get("created_at"),
        "is_debit": bool(row.get("is_debit", 1)),
    }


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/")
def list_cards(user: dict = Depends(get_current_user)):
    """Lista todos os cartões do utilizador.
    Se o utilizador não tiver cartões, cria automaticamente um cartão de débito BankAO.
    """
    import random as _rnd
    conn = get_connection()

    rows = conn.execute(
        "SELECT * FROM cards WHERE user_id = ? ORDER BY created_at DESC",
        (user["id"],)
    ).fetchall()

    # Auto-provisionar cartão de débito se o utilizador ainda não tiver nenhum
    if not rows:
        acc = conn.execute(
            "SELECT id FROM accounts WHERE user_id = ? AND currency = 'AOA' LIMIT 1",
            (user["id"],)
        ).fetchone()
        if acc:
            card_id = str(uuid.uuid4())
            last_four = str(_rnd.randint(1000, 9999))
            user_row = conn.execute("SELECT nome FROM users WHERE id = ?", (user["id"],)).fetchone()
            cardholder = (user_row["nome"] if user_row else "CLIENTE BANKAO").upper()
            with conn:
                conn.execute("""
                    INSERT OR IGNORE INTO cards (
                        id, user_id, account_id, card_type, network, last_four,
                        cardholder_name, expires_month, expires_year, status,
                        is_virtual, color_scheme, institution
                    ) VALUES (?, ?, ?, 'debit', 'multicaixa', ?, ?, 12, 2028, 'active', 0, 'blue', 'BankAO')
                """, (card_id, user["id"], acc["id"], last_four, cardholder))
            rows = conn.execute(
                "SELECT * FROM cards WHERE user_id = ? ORDER BY created_at DESC",
                (user["id"],)
            ).fetchall()

    conn.close()
    return {"cards": [_format_card(dict(r)) for r in rows]}



@router.get("/{card_id}")
def get_card_detail(card_id: str, user: dict = Depends(get_current_user)):
    """Detalhe completo de um cartão."""
    conn = get_connection()
    card = _get_card(conn, card_id, user["id"])
    conn.close()
    return _format_card(card)


@router.post("/{card_id}/control")
def card_control(card_id: str, body: CardControlIn, user: dict = Depends(get_current_user)):
    """Bloquear, desbloquear ou cancelar cartão."""
    valid = {"block", "unblock", "cancel"}
    if body.action not in valid:
        raise HTTPException(400, detail=f"Ação inválida. Escolha entre: {', '.join(valid)}")

    conn = get_connection()
    card = _get_card(conn, card_id, user["id"])

    if card["status"] == "cancelled":
        conn.close()
        raise HTTPException(400, detail="Cartão já cancelado. Não pode ser reativado.")

    if body.action == "cancel" and card["is_virtual"]:
        new_status = "cancelled"
    elif body.action == "block":
        new_status = "blocked"
    elif body.action == "unblock":
        if card["status"] == "cancelled":
            conn.close()
            raise HTTPException(400, detail="Cartão cancelado não pode ser desbloqueado.")
        new_status = "active"
    else:  # cancel
        new_status = "cancelled"

    with conn:
        conn.execute(
            "UPDATE cards SET status = ? WHERE id = ?",
            (new_status, card_id)
        )
        # Registar notificação
        action_labels = {"block": "bloqueado", "unblock": "desbloqueado", "cancel": "cancelado"}
        conn.execute(
            """INSERT INTO card_notifications (id, user_id, card_id, type, title, message)
               VALUES (?, ?, ?, 'controlo', ?, ?)""",
            (str(uuid.uuid4()), user["id"], card_id,
             f"Cartão {action_labels[body.action]}",
             f"O cartão terminado em {card['last_four']} foi {action_labels[body.action]} com sucesso."
             + (f" Motivo: {body.reason}" if body.reason else ""))
        )
    conn.close()
    return {"status": new_status, "message": f"Cartão {action_labels[body.action]} com sucesso."}


@router.patch("/{card_id}/settings")
def update_card_settings(card_id: str, body: CardSettingsIn, user: dict = Depends(get_current_user)):
    """Atualizar definições e limites do cartão."""
    conn = get_connection()
    card = _get_card(conn, card_id, user["id"])

    if card["status"] == "cancelled":
        conn.close()
        raise HTTPException(400, detail="Cartão cancelado. Definições não podem ser alteradas.")

    updates = {}
    if body.online_payments is not None:
        updates["online_payments"] = int(body.online_payments)
    if body.international_payments is not None:
        updates["international_payments"] = int(body.international_payments)
    if body.atm_withdrawals is not None:
        updates["atm_withdrawals"] = int(body.atm_withdrawals)
    if body.contactless is not None:
        updates["contactless"] = int(body.contactless)
    if body.daily_limit_minor is not None:
        if body.daily_limit_minor < 0:
            conn.close()
            raise HTTPException(400, detail="Limite diário não pode ser negativo.")
        updates["daily_limit_minor"] = body.daily_limit_minor
    if body.monthly_limit_minor is not None:
        if body.monthly_limit_minor < 0:
            conn.close()
            raise HTTPException(400, detail="Limite mensal não pode ser negativo.")
        updates["monthly_limit_minor"] = body.monthly_limit_minor

    if not updates:
        conn.close()
        return {"message": "Nenhuma definição alterada."}

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with conn:
        conn.execute(f"UPDATE cards SET {set_clause} WHERE id = ?", list(updates.values()) + [card_id])
    conn.close()
    return {"message": "Definições atualizadas com sucesso.", "updated": list(updates.keys())}


@router.post("/virtual/create")
def create_virtual_card(body: VirtualCardIn, user: dict = Depends(get_current_user)):
    """Criar um cartão virtual (BankAO)."""
    conn = get_connection()

    # Verificar que a conta existe e pertence ao utilizador
    acc = conn.execute(
        "SELECT * FROM accounts WHERE id = ? AND user_id = ?",
        (body.account_id, user["id"])
    ).fetchone()
    if not acc:
        conn.close()
        raise HTTPException(404, detail="Conta não encontrada.")

    # Gerar dados do cartão virtual
    import random
    card_id = str(uuid.uuid4())
    last_four = str(random.randint(1000, 9999))
    expires_date = datetime.date.today() + datetime.timedelta(days=body.expires_in_days)
    color_schemes = ["blue", "purple", "green", "dark", "gold"]

    user_row = conn.execute("SELECT nome FROM users WHERE id = ?", (user["id"],)).fetchone()
    cardholder = (user_row["nome"] if user_row else "Cliente BankAO").upper()

    with conn:
        conn.execute("""
            INSERT INTO cards (
                id, user_id, account_id, card_type, network, last_four,
                cardholder_name, expires_month, expires_year, status,
                is_virtual, is_single_use, label, color_scheme,
                online_payments, international_payments, atm_withdrawals, contactless,
                daily_limit_minor, monthly_limit_minor, currency, institution
            ) VALUES (?, ?, ?, 'virtual', 'visa', ?, ?, ?, ?, 'active',
                      1, ?, ?, ?, 1, 1, 0, 1, ?, ?, ?, 'BankAO')
        """, (
            card_id, user["id"], body.account_id, last_four,
            cardholder, expires_date.month, expires_date.year,
            int(body.single_use), body.label or "Cartão Virtual",
            color_schemes[hash(card_id) % len(color_schemes)],
            body.spending_limit_minor or 50_000_000,  # 500.000 AOA default
            body.spending_limit_minor or 200_000_000,  # 2.000.000 AOA mensal
            dict(acc)["currency"] or "AOA"
        ))
        conn.execute(
            """INSERT INTO card_notifications (id, user_id, card_id, type, title, message)
               VALUES (?, ?, ?, 'virtual_criado', ?, ?)""",
            (str(uuid.uuid4()), user["id"], card_id,
             "Cartão virtual criado",
             f"O cartão virtual «{body.label}» terminado em {last_four} foi criado com sucesso.")
        )
    conn.close()
    return {"card_id": card_id, "last_four": last_four, "message": "Cartão virtual criado com sucesso."}


@router.get("/{card_id}/movements")
def card_movements(
    card_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    op_type: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    """Histórico de movimentos de um cartão."""
    conn = get_connection()
    _get_card(conn, card_id, user["id"])  # verificar ownership

    query = "SELECT * FROM card_movements WHERE card_id = ?"
    params: list = [card_id]
    if op_type:
        query += " AND operation_type = ?"
        params.append(op_type)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    rows = conn.execute(query, params).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM card_movements WHERE card_id = ?" +
        (" AND operation_type = ?" if op_type else ""),
        [card_id] + ([op_type] if op_type else [])
    ).fetchone()[0]
    conn.close()
    return {
        "movements": [_format_movement(dict(r)) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{card_id}/spending")
def card_spending_summary(card_id: str, user: dict = Depends(get_current_user)):
    """Resumo de despesas: total mensal, por categoria e evolução diária."""
    conn = get_connection()
    _get_card(conn, card_id, user["id"])

    today = datetime.date.today()
    month_start = today.replace(day=1).isoformat()

    # Total do mês corrente
    monthly_total = conn.execute("""
        SELECT COALESCE(SUM(amount_minor), 0) FROM card_movements
        WHERE card_id = ? AND is_debit = 1 AND status = 'completed'
          AND DATE(created_at) >= ?
    """, (card_id, month_start)).fetchone()[0]

    # Por categoria
    cats = conn.execute("""
        SELECT merchant_category, COALESCE(SUM(amount_minor), 0) as total
        FROM card_movements
        WHERE card_id = ? AND is_debit = 1 AND status = 'completed'
          AND DATE(created_at) >= ?
        GROUP BY merchant_category ORDER BY total DESC
    """, (card_id, month_start)).fetchall()

    # Evolução dos últimos 30 dias
    daily = conn.execute("""
        SELECT DATE(created_at) as day, COALESCE(SUM(amount_minor), 0) as total
        FROM card_movements
        WHERE card_id = ? AND is_debit = 1 AND status = 'completed'
          AND DATE(created_at) >= DATE('now', '-30 days')
        GROUP BY day ORDER BY day ASC
    """, (card_id,)).fetchall()

    stats = conn.execute("""
        SELECT COUNT(*) AS n, COALESCE(MAX(amount_minor), 0) AS biggest
        FROM card_movements
        WHERE card_id = ? AND is_debit = 1 AND status = 'completed'
          AND DATE(created_at) >= ?
    """, (card_id, month_start)).fetchone()
    biggest_row = conn.execute("""
        SELECT merchant_name FROM card_movements
        WHERE card_id = ? AND is_debit = 1 AND status = 'completed'
          AND DATE(created_at) >= ?
        ORDER BY amount_minor DESC LIMIT 1
    """, (card_id, month_start)).fetchone()

    prev_start = (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1).isoformat()
    prev_total = conn.execute("""
        SELECT COALESCE(SUM(amount_minor), 0) FROM card_movements
        WHERE card_id = ? AND is_debit = 1 AND status = 'completed'
          AND DATE(created_at) >= ? AND DATE(created_at) < ?
    """, (card_id, prev_start, month_start)).fetchone()[0]

    conn.close()
    return {
        "monthly_total": _to_decimal(monthly_total),
        "tx_count": stats["n"],
        "biggest_amount": _to_decimal(stats["biggest"]),
        "biggest_merchant": biggest_row["merchant_name"] if biggest_row else None,
        "avg_daily": _to_decimal(int(monthly_total / max(today.day, 1))),
        "prev_month_total": _to_decimal(prev_total),
        "month_start": month_start,
        "by_category": [
            {"category": r["merchant_category"], "total": _to_decimal(r["total"])}
            for r in cats
        ],
        "daily_evolution": [
            {"day": r["day"], "total": _to_decimal(r["total"])}
            for r in daily
        ],
    }


@router.get("/notifications/list")
def list_notifications(user: dict = Depends(get_current_user)):
    """Lista todas as notificações de cartão do utilizador."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM card_notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
        (user["id"],)
    ).fetchall()
    conn.close()
    return {
        "notifications": [
            {
                "id": r["id"],
                "card_id": r["card_id"],
                "type": r["type"],
                "title": r["title"],
                "message": r["message"],
                "is_read": bool(r["is_read"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
        "unread_count": sum(1 for r in rows if not r["is_read"]),
    }


@router.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: str, user: dict = Depends(get_current_user)):
    """Marcar notificação como lida."""
    conn = get_connection()
    with conn:
        updated = conn.execute(
            "UPDATE card_notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notif_id, user["id"])
        ).rowcount
    conn.close()
    if updated == 0:
        raise HTTPException(404, detail="Notificação não encontrada.")
    return {"message": "Notificação marcada como lida."}


@router.post("/notifications/read-all")
def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    """Marcar todas as notificações de cartão como lidas."""
    conn = get_connection()
    with conn:
        updated = conn.execute(
            "UPDATE card_notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user["id"],)
        ).rowcount
    conn.close()
    return {"message": "Notificações marcadas como lidas.", "updated": updated}
