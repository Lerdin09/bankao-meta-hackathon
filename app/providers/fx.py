"""
Motor de Câmbio e Cotações do Bankão.
Suporte para conversão transparente entre AOA (Kwanza), EUR (Euro) e USD (Dólar).
"""
from typing import Dict, Any
from app.db import get_connection

class FXProvider:
    @staticmethod
    def get_quote(from_currency: str, to_currency: str, amount_minor: int) -> Dict[str, Any]:
        """
        Calcula a cotação, taxa de serviço e valor líquido que o destinatário recebe.
        """
        from_cur = from_currency.upper()
        to_cur = to_currency.upper()

        if from_cur == to_cur:
            return {
                "from_currency": from_cur,
                "to_currency": to_cur,
                "source_amount_minor": amount_minor,
                "dest_amount_minor": amount_minor,
                "rate": 1.0,
                "fee_minor": 0,
                "fee_percentage": 0.0,
            }

        with get_connection() as conn:
            row = conn.execute(
                "SELECT rate, fee_percentage FROM fx_rates WHERE base_currency = ? AND quote_currency = ?",
                (from_cur, to_cur)
            ).fetchone()

            if not row:
                # Tenta o inverso
                inv = conn.execute(
                    "SELECT rate, fee_percentage FROM fx_rates WHERE base_currency = ? AND quote_currency = ?",
                    (to_cur, from_cur)
                ).fetchone()
                if inv and inv["rate"] > 0:
                    rate = 1.0 / inv["rate"]
                    fee_pct = inv["fee_percentage"]
                else:
                    raise ValueError(f"Par cambial não suportado: {from_cur}/{to_cur}")
            else:
                rate = row["rate"]
                fee_pct = row["fee_percentage"]

        fee_minor = int(round(amount_minor * fee_pct))
        net_source_minor = max(0, amount_minor - fee_minor)
        
        # Conversão em minor units
        dest_amount_minor = int(round(net_source_minor * rate))

        return {
            "from_currency": from_cur,
            "to_currency": to_cur,
            "source_amount_minor": amount_minor,
            "source_amount_decimal": amount_minor / 100.0,
            "rate": rate,
            "fee_minor": fee_minor,
            "fee_decimal": fee_minor / 100.0,
            "fee_percentage": fee_pct * 100,
            "dest_amount_minor": dest_amount_minor,
            "dest_amount_decimal": dest_amount_minor / 100.0,
        }
