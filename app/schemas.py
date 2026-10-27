"""
Modelos de validação de dados Pydantic para a API do Bankão.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any

# Auth
class UserRegister(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    telefone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

# Contas
class AccountResponse(BaseModel):
    id: str
    user_id: str
    account_number: str
    iban_virtual: str
    currency: str
    status: str
    balance_minor: int
    balance_decimal: float

# Depósitos
class DepositReferenciaCreate(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0, description="Valor em Kwanza ou Euro")

class DepositExpressCreate(BaseModel):
    account_id: str
    amount: float = Field(..., gt=0)
    phone_number: str = Field(..., min_length=9, max_length=15)

class DepositSimulatePayment(BaseModel):
    deposit_id: str

# Transferências
class InternalTransferCreate(BaseModel):
    from_account_id: str
    to_account_number: str
    amount: float = Field(..., gt=0)
    description: Optional[str] = "Transferência interna Bankão"
    idempotency_key: str

class IbanTransferCreate(BaseModel):
    from_account_id: str
    to_iban: str
    beneficiary_name: str
    amount: float = Field(..., gt=0)
    dest_currency: str = "EUR"
    idempotency_key: str

# Câmbio
class FxQuoteRequest(BaseModel):
    from_currency: str
    to_currency: str
    amount: float = Field(..., gt=0)

# IA / Assistente
class AIChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None

class AIExplainTransferRequest(BaseModel):
    source_amount: float
    source_currency: str
    dest_amount: float
    dest_currency: str
    fx_rate: float
    fee: float
    dest_iban: str
    beneficiary_name: str
