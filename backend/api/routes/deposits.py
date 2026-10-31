"""
Rotas — Depósitos: Depósitos por Referência e Multicaixa Express.
"""

from fastapi import APIRouter, Depends, HTTPException

from backend.core.security import get_current_user
from backend.providers.deposits import DepositProvider
from backend.schemas import DepositExpressCreate, DepositReferenciaCreate, DepositSimulatePayment
from backend.services.ledger import credit_deposit

router = APIRouter(prefix="/api/deposits", tags=["Depósitos"])


@router.post("/referencia")
def criar_deposito_referencia(
    data: DepositReferenciaCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    res = DepositProvider.criar_deposito_referencia(data.account_id, amount_minor, "AOA")
    return res


@router.post("/multicaixa-express")
def criar_deposito_multicaixa_express(
    data: DepositExpressCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    res = DepositProvider.criar_deposito_multicaixa_express(data.account_id, amount_minor, data.phone_number, "AOA")
    return res


@router.post("/simulate-payment")
def simular_pagamento(data: DepositSimulatePayment):
    """Simula a confirmação de pagamento do Multicaixa Express ou Referência."""
    try:
        result = credit_deposit(data.deposit_id)
        return {
            "success": True,
            "message": "Pagamento confirmado com sucesso! Saldo creditado na sua carteira.",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
