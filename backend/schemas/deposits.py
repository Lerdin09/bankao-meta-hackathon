"""
Modelos Pydantic — Depósitos (Referência e Multicaixa Express).
"""
from pydantic import BaseModel, Field


class DepositReferenciaCreate(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0, description="Valor em Kwanza ou Euro")


class DepositExpressCreate(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0)
    phone_number: str = Field(..., min_length=9, max_length=15)


class DepositSimulatePayment(BaseModel):
    deposit_id: str
