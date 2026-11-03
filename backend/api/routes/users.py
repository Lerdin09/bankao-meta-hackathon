"""
Rotas — Utilizadores: Pesquisa de destinatários (por e-mail ou por número de conta BankAO).
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.core.security import get_current_user
from backend.database import get_connection

router = APIRouter(prefix="/api/users", tags=["Utilizadores"])


def _nome_completo(u) -> str:
    nome = u["nome"]
    if not nome or nome == "Novo Utilizador":
        nome = f"{u['primeiro_nome'] or ''} {u['ultimo_nome'] or ''}".strip() or u["email"]
    return nome


@router.get("/lookup")
def lookup_user(email: Optional[str] = None, account: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    if not email and not account:
        raise HTTPException(status_code=422, detail="Indique o e-mail ou o número da conta.")
    with get_connection() as conn:
        if email:
            u = conn.execute(
                "SELECT id, nome, primeiro_nome, ultimo_nome, email FROM users WHERE lower(email) = lower(?)",
                (email.strip(),)
            ).fetchone()
            if not u:
                return {"found": False}
            return {"found": True, "id": u["id"], "nome": _nome_completo(u), "email": u["email"]}

        # Número de conta: só devolve o titular (nunca o e-mail de terceiros)
        digits = re.sub(r"\D", "", account)
        u = conn.execute(
            "SELECT u.id, u.nome, u.primeiro_nome, u.ultimo_nome, u.email FROM accounts a "
            "JOIN users u ON u.id = a.user_id WHERE a.account_number = ?",
            (digits,)
        ).fetchone()
        if not u:
            return {"found": False}
        return {"found": True, "id": u["id"], "nome": _nome_completo(u)}
