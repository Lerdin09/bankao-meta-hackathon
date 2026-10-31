"""
Modelos Pydantic — Câmbio e cotações.
"""
from pydantic import BaseModel, Field


class FxQuoteRequest(BaseModel):
    from_currency: str
    to_currency: str
    amount: float = Field(..., gt=0)
