"""
Modelos Pydantic — Transferências internas e para IBAN.
"""
from typing import Optional
from pydantic import BaseModel, Field


class InternalTransferCreate(BaseModel):
    from_account_id: str
    to_account_number: Optional[str] = None
    to_email: Optional[str] = None
    amount: float = Field(..., gt=0)
    description: Optional[str] = "Transferência interna BankAO"
    idempotency_key: str


class IbanTransferCreate(BaseModel):
    from_account_id: str
    to_iban: str
    beneficiary_name: str
    amount: float = Field(..., gt=0)
    dest_currency: str = "EUR"
    idempotency_key: str
