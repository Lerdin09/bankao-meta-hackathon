"""
Modelos de validação (Pydantic) da API, organizados por domínio.
Tudo é reexportado aqui: `from backend.schemas import UserLogin`.
"""
from backend.schemas.auth import UserRegister, UserLogin, TokenResponse
from backend.schemas.kyc import KYCExtractRequest, KYCConfirmRequest
from backend.schemas.accounts import AccountResponse
from backend.schemas.deposits import DepositReferenciaCreate, DepositExpressCreate, DepositSimulatePayment
from backend.schemas.transfers import InternalTransferCreate, IbanTransferCreate
from backend.schemas.fx import FxQuoteRequest
from backend.schemas.ai import AIChatRequest, AIExplainTransferRequest, IdealPaceRequest

__all__ = [
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "KYCExtractRequest",
    "KYCConfirmRequest",
    "AccountResponse",
    "DepositReferenciaCreate",
    "DepositExpressCreate",
    "DepositSimulatePayment",
    "InternalTransferCreate",
    "IbanTransferCreate",
    "FxQuoteRequest",
    "AIChatRequest",
    "AIExplainTransferRequest",
    "IdealPaceRequest",
]
