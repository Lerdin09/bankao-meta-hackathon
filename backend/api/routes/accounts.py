"""
Rotas — Contas: Contas e carteiras do utilizador.
"""

from fastapi import APIRouter, Depends

from backend.core.security import get_current_user
from backend.services.ledger import get_user_accounts

router = APIRouter(prefix="/api/accounts", tags=["Contas"])


@router.get("")
def get_accounts(current_user: dict = Depends(get_current_user)):
    accounts = get_user_accounts(current_user["id"])
    return accounts
