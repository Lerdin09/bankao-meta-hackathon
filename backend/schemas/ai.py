"""
Modelos Pydantic — Assistente de IA (Copilot).
"""
from typing import List, Optional
from pydantic import BaseModel


class AIChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None
    # Pedido a meio (ex.: a IA perguntou o prazo da meta); o frontend devolve-o na mensagem seguinte
    pending: Optional[dict] = None


class AIExplainTransferRequest(BaseModel):
    source_amount: float
    source_currency: str
    dest_amount: float
    dest_currency: str
    fx_rate: float
    fee: float
    dest_iban: str
    beneficiary_name: str


class IdealPaceGoal(BaseModel):
    name: Optional[str] = None
    target: float = 0
    saved: float = 0
    monthly: float = 0
    deadline: Optional[str] = None


class IdealPaceRequest(BaseModel):
    currency: str = "AOA"
    income_month: float = 0
    expense_month: float = 0
    budget_month: float = 0
    goals: List[IdealPaceGoal] = []
