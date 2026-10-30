"""
Modelos de validação de dados Pydantic para a API do BankAO.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any

# Auth
class UserRegister(BaseModel):
    email: EmailStr
    telefone: str
    password: str = Field(..., min_length=6)
    confirm_password: Optional[str] = None
    terms_accepted: bool = Field(default=True)
    nome: Optional[str] = "Novo Utilizador"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

# KYC / Verificação de Identidade com IA
class KYCExtractRequest(BaseModel):
    doc_type: str = Field(..., description="'bilhete' ou 'passaporte'")
    foto_frente: str = Field(..., description="Imagem base64 da frente ou página de dados")
    foto_verso: str = Field(..., description="Imagem base64 do verso ou página de assinatura")

class KYCConfirmRequest(BaseModel):
    nome_completo: str
    primeiro_nome: str
    ultimo_nome: str
    nome_pai: Optional[str] = ""
    nome_mae: Optional[str] = ""
    doc_tipo: str = "bilhete"
    doc_numero: str
    morada: Optional[str] = ""
    data_emissao: Optional[str] = ""

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
