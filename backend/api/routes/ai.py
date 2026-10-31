"""
Rotas — Assistente IA: Copilot, explicação de transferências e análise de risco.
"""

from fastapi import APIRouter, Depends

from backend.ai.assistant import BankaoAssistant
from backend.core.config import settings
from backend.core.security import get_current_user
from backend.schemas import AIChatRequest, AIExplainTransferRequest

router = APIRouter(prefix="/api/ai", tags=["Assistente IA"])


@router.post("/chat")
def ai_chat(data: AIChatRequest):
    res = BankaoAssistant.chat_with_action(data.message, data.history)
    return {
        "reply": res["reply"],
        "action": res.get("action"),
        "model": settings.MODEL_NAME,
        "provider": "Meta Model API / Muse Spark"
    }


@router.post("/explain-transfer")
def ai_explain_transfer(data: AIExplainTransferRequest):
    explanation = BankaoAssistant.explain_transfer(
        source_amount=data.source_amount,
        source_currency=data.source_currency,
        dest_amount=data.dest_amount,
        dest_currency=data.dest_currency,
        fx_rate=data.fx_rate,
        fee=data.fee,
        dest_iban=data.dest_iban,
        beneficiary_name=data.beneficiary_name
    )
    return {
        "explanation": explanation,
        "model": settings.MODEL_NAME
    }


@router.get("/analyze-risk")
def ai_analyze_risk(
    amount: float,
    currency: str,
    tx_type: str,
    current_user: dict = Depends(get_current_user)
):
    analysis = BankaoAssistant.analyze_risk(
        amount=amount,
        currency=currency,
        tx_type=tx_type,
        user_kyc_status=current_user.get("kyc_status", "verificado")
    )
    return analysis
