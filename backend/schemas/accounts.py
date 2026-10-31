"""
Modelos Pydantic — Contas e carteiras.
"""
from pydantic import BaseModel


class AccountResponse(BaseModel):
    id: str
    user_id: str
    account_number: str
    iban_virtual: str
    currency: str
    status: str
    balance_minor: int
    balance_decimal: float
