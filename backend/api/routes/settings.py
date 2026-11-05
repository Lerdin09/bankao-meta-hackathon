"""
Rotas — Definições do utilizador.
Dados sensíveis (IBAN, nº de conta, NIF/documento) só em leitura.
"""
import re
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.core.security import get_current_user, get_password_hash, verify_password
from backend.database import get_connection
from backend.services import user_settings as us
from backend.services.audit import write_audit_log
from backend.services.email import send_support_ticket_email

router = APIRouter(prefix="/api/settings", tags=["Definições"])


def _mask(v: Optional[str], keep: int = 3) -> str:
    v = v or ""
    return ("•" * max(0, len(v) - keep) + v[-keep:]) if v else ""


def _profile(u: dict) -> dict:
    nome = u.get("nome")
    if not nome or nome == "Novo Utilizador":
        nome = f"{u.get('primeiro_nome') or ''} {u.get('ultimo_nome') or ''}".strip() or u["email"]
    return {
        "nome": nome, "email": u["email"], "telefone": u.get("telefone") or "", "morada": u.get("morada") or "",
        "kyc_status": u.get("kyc_status"),
        # Só leitura (mascarados)
        "doc_tipo": u.get("doc_tipo"), "doc_numero_masked": _mask(u.get("doc_numero"), 3),
        "protected": ["nome", "doc_tipo", "doc_numero", "iban", "account_number", "kyc_status"],
    }


@router.get("")
def read_settings(user: dict = Depends(get_current_user)):
    us.ensure_tables()
    with get_connection() as c:
        pin = c.execute("SELECT pin_hash FROM user_settings WHERE user_id = ?", (user["id"],)).fetchone()
        accs = c.execute("SELECT id, account_number, iban_virtual, currency, status FROM accounts WHERE user_id = ? ORDER BY currency", (user["id"],)).fetchall()
        n_sess = c.execute("SELECT COUNT(*) n FROM user_sessions WHERE user_id = ? AND revoked = 0", (user["id"],)).fetchone()["n"]
    return {
        "settings": us.get_settings(user["id"]),
        "profile": _profile(user),
        "has_pin": bool(pin and pin["pin_hash"]),
        "sessions": n_sess,
        "accounts": [{"id": a["id"], "currency": a["currency"], "status": a["status"],
                      "account_number": a["account_number"], "iban": a["iban_virtual"]} for a in accs],
        "locked": bool(accs) and all(a["status"] != "active" for a in accs),
    }


class SettingsPatch(BaseModel):
    values: Dict[str, Any]


@router.put("")
def update_settings(body: SettingsPatch, user: dict = Depends(get_current_user)):
    saved = us.save_settings(user["id"], body.values)
    write_audit_log(user["id"], "settings.update", list(body.values.keys()))
    return {"settings": saved}


class ProfilePatch(BaseModel):
    telefone: Optional[str] = None
    email: Optional[str] = None
    morada: Optional[str] = None

    model_config = {"extra": "forbid"}   # qualquer outro campo (NIF, IBAN, conta…) é recusado


@router.patch("/profile")
def update_profile(body: ProfilePatch, user: dict = Depends(get_current_user)):
    sets, vals = [], []
    if body.telefone is not None:
        tel = re.sub(r"[\s\-]", "", body.telefone)
        if not re.fullmatch(r"\+?\d{9,15}", tel):
            raise HTTPException(400, "Número de telefone inválido.")
        sets.append("telefone = ?"); vals.append(tel)
    if body.email is not None:
        em = body.email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", em):
            raise HTTPException(400, "E-mail inválido.")
        with get_connection() as c:
            if c.execute("SELECT 1 FROM users WHERE lower(email) = ? AND id != ?", (em, user["id"])).fetchone():
                raise HTTPException(400, "Este e-mail já está em uso.")
        sets.append("email = ?"); vals.append(em)
    if body.morada is not None:
        if len(body.morada) > 200:
            raise HTTPException(400, "Endereço demasiado longo.")
        sets.append("morada = ?"); vals.append(body.morada.strip())
    if not sets:
        raise HTTPException(400, "Nada para atualizar.")
    with get_connection() as c:
        c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", (*vals, user["id"]))
        row = c.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    write_audit_log(user["id"], "profile.update", [s.split(" ")[0] for s in sets])
    return {"profile": _profile(dict(row))}


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/password")
def change_password(body: PasswordIn, user: dict = Depends(get_current_user)):
    with get_connection() as c:
        row = c.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(400, "A palavra-passe atual está incorreta.")
        n = body.new_password
        if len(n) < 8 or not re.search(r"[A-Za-z]", n) or not re.search(r"\d", n):
            raise HTTPException(400, "A nova palavra-passe deve ter pelo menos 8 caracteres, com letras e números.")
        if verify_password(n, row["password_hash"]):
            raise HTTPException(400, "A nova palavra-passe deve ser diferente da atual.")
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (get_password_hash(n), user["id"]))
    write_audit_log(user["id"], "password.change")
    return {"ok": True}


class PinIn(BaseModel):
    pin: str
    current_pin: Optional[str] = None


@router.post("/pin")
def set_pin(body: PinIn, user: dict = Depends(get_current_user)):
    if not re.fullmatch(r"\d{4,6}", body.pin):
        raise HTTPException(400, "O PIN deve ter 4 a 6 dígitos.")
    us.ensure_tables()
    with get_connection() as c:
        row = c.execute("SELECT pin_hash FROM user_settings WHERE user_id = ?", (user["id"],)).fetchone()
        if row and row["pin_hash"]:
            if not body.current_pin or not verify_password(body.current_pin, row["pin_hash"]):
                raise HTTPException(400, "O PIN atual está incorreto.")
        h = get_password_hash(body.pin)
        c.execute("""INSERT INTO user_settings (user_id, data, pin_hash) VALUES (?, '{}', ?)
                     ON CONFLICT(user_id) DO UPDATE SET pin_hash = excluded.pin_hash""", (user["id"], h))
    write_audit_log(user["id"], "pin.set")
    return {"ok": True}


@router.post("/pin/verify")
def verify_pin(body: PinIn, user: dict = Depends(get_current_user)):
    with get_connection() as c:
        row = c.execute("SELECT pin_hash FROM user_settings WHERE user_id = ?", (user["id"],)).fetchone()
    return {"ok": bool(row and row["pin_hash"] and verify_password(body.pin, row["pin_hash"]))}


@router.get("/sessions")
def list_sessions(request: Request, user: dict = Depends(get_current_user)):
    with get_connection() as c:
        rows = c.execute("""SELECT id, device, ip, created_at, last_seen FROM user_sessions
                            WHERE user_id = ? AND revoked = 0 ORDER BY last_seen DESC""", (user["id"],)).fetchall()
    return {"sessions": [dict(r) for r in rows], "current": user.get("_sid")}


@router.delete("/sessions/{sid}")
def revoke_session(sid: str, user: dict = Depends(get_current_user)):
    with get_connection() as c:
        c.execute("UPDATE user_sessions SET revoked = 1 WHERE id = ? AND user_id = ?", (sid, user["id"]))
    return {"ok": True}


@router.post("/sessions/revoke-others")
def revoke_others(user: dict = Depends(get_current_user)):
    with get_connection() as c:
        c.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ? AND id != ?", (user["id"], user.get("_sid") or ""))
    return {"ok": True}


@router.get("/login-history")
def login_history(user: dict = Depends(get_current_user)):
    us.ensure_tables()
    with get_connection() as c:
        rows = c.execute("SELECT device, ip, success, created_at FROM login_history WHERE user_id = ? ORDER BY id DESC LIMIT 20", (user["id"],)).fetchall()
    return {"history": [dict(r) for r in rows]}


class LockIn(BaseModel):
    lock: bool
    password: str


@router.post("/account-lock")
def account_lock(body: LockIn, user: dict = Depends(get_current_user)):
    with get_connection() as c:
        row = c.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not verify_password(body.password, row["password_hash"]):
            raise HTTPException(400, "Palavra-passe incorreta.")
        c.execute("UPDATE accounts SET status = ? WHERE user_id = ? AND status IN ('active','blocked')",
                  ("blocked" if body.lock else "active", user["id"]))
    write_audit_log(user["id"], "account.lock" if body.lock else "account.unlock")
    return {"locked": body.lock}


class SupportIn(BaseModel):
    kind: str          # problema | fraude | suporte | encerramento
    message: str = ""


@router.post("/support")
def support(body: SupportIn, user: dict = Depends(get_current_user)):
    if body.kind not in ("problema", "fraude", "suporte", "encerramento"):
        raise HTTPException(400, "Tipo de pedido inválido.")
    if body.kind != "encerramento" and len(body.message.strip()) < 5:
        raise HTTPException(400, "Descreva brevemente o assunto.")
    us.ensure_tables()
    rid = "REQ-" + uuid.uuid4().hex[:8].upper()
    with get_connection() as c:
        c.execute("INSERT INTO support_requests (id, user_id, kind, message) VALUES (?, ?, ?, ?)",
                  (rid, user["id"], body.kind, body.message.strip()[:1000]))
    write_audit_log(user["id"], f"support.{body.kind}", rid)

    # Encaminhar imediatamente por e-mail para o canal oficial de suporte
    user_name = user.get("nome") or user.get("primeiro_nome") or "Cliente BankAO"
    user_email = user.get("email") or ""
    user_phone = user.get("telefone") or ""
    send_support_ticket_email(
        request_id=rid,
        user_name=user_name,
        user_email=user_email,
        user_phone=user_phone,
        kind=body.kind,
        message=body.message.strip()
    )

    return {"id": rid}
