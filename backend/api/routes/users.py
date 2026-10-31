"""
Rotas — Utilizadores: Pesquisa de destinatários.
"""

from fastapi import APIRouter, Depends

from backend.core.security import get_current_user
from backend.database import get_connection

router = APIRouter(prefix="/api/users", tags=["Utilizadores"])


@router.get("/lookup")
def lookup_user(email: str, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        u = conn.execute(
            "SELECT id, nome, primeiro_nome, ultimo_nome, email FROM users WHERE lower(email) = lower(?)",
            (email.strip(),)
        ).fetchone()
        if not u:
            return {"found": False}
        nome_completo = u["nome"]
        if not nome_completo or nome_completo == "Novo Utilizador":
            nome_completo = f"{u['primeiro_nome'] or ''} {u['ultimo_nome'] or ''}".strip() or u["email"]
        return {
            "found": True,
            "id": u["id"],
            "nome": nome_completo,
            "email": u["email"]
        }
