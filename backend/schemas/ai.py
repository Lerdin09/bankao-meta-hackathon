"""
Modelos Pydantic — Assistente de IA (Copilot).
"""
from typing import List, Optional
from pydantic import BaseModel


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
