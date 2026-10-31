"""
Rotas — Câmbio: Cotações de câmbio.
"""

from fastapi import APIRouter, HTTPException

from backend.providers.fx import FXProvider
from backend.schemas import FxQuoteRequest

router = APIRouter(prefix="/api/fx", tags=["Câmbio"])


@router.post("/quote")
def get_fx_quote(data: FxQuoteRequest):
    amount_minor = int(round(data.amount * 100))
    try:
        quote = FXProvider.get_quote(data.from_currency, data.to_currency, amount_minor, custom_fee_pct=0.025)
        return quote
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
