"""
Rotas — Câmbio: Cotações de câmbio.
"""

from fastapi import APIRouter, HTTPException

from backend.database import get_connection
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


@router.get("/rates")
def get_fx_rates():
    """Taxas de referência guardadas na base de dados (fonte única de câmbio do frontend)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT base_currency, quote_currency, rate FROM fx_rates").fetchall()
    return {f"{r['base_currency']}_{r['quote_currency']}": r["rate"] for r in rows}
