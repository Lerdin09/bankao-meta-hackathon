"""
Rotas — Extrato: Histórico de movimentos.
"""

from fastapi import APIRouter, Depends

from backend.core.security import get_current_user
from backend.database import get_connection

router = APIRouter(prefix="/api/transactions", tags=["Extrato"])


def _mask(value):
    """Mostra apenas o início e o fim de um identificador (IBAN / nº de conta)."""
    if not value:
        return None
    v = str(value).replace(" ", "")
    if len(v) <= 10:
        return v
    return f"{v[:4]} •••• {v[-4:]}"


def _counterparty(r):
    """
    Descreve a outra ponta do movimento:
      - amount < 0  → dinheiro SAIU  → 'to'   (para onde foi)
      - amount > 0  → dinheiro ENTROU → 'from' (de onde veio)
    """
    is_credit = r["amount_minor"] > 0
    ttype = r["type"]

    if ttype == "deposit":
        method = r["dep_method"]
        label = {
            "multicaixa_express": "Multicaixa Express",
            "referencia": "Referência Multicaixa",
        }.get(method, "Depósito")
        ref = r["dep_reference_code"] or r["dep_phone_number"]
        return {
            "direction": "from",
            "kind": "deposit",
            "name": label,
            "ref_label": "Referência" if r["dep_reference_code"] else "Telemóvel",
            "ref": ref,
            "extra": f"Entidade {r['dep_entidade_code']}" if r["dep_entidade_code"] else None,
        }

    if ttype == "transfer_iban":
        return {
            "direction": "to",
            "kind": "iban",
            "name": r["tr_beneficiary_name"],
            "ref_label": "IBAN",
            "ref": _mask(r["tr_to_iban"]),
            "extra": None,
        }

    if ttype == "transfer_internal":
        if is_credit:
            return {
                "direction": "from",
                "kind": "internal",
                "name": r["from_owner_name"] or "Conta BankAO",
                "ref_label": "Conta",
                "ref": _mask(r["from_iban"] or r["from_account_number"]),
                "extra": None,
            }
        return {
            "direction": "to",
            "kind": "internal",
            "name": r["to_owner_name"] or r["tr_beneficiary_name"] or "Conta BankAO",
            "ref_label": "Conta",
            "ref": _mask(r["to_iban_virtual"] or r["to_account_number"]),
            "extra": None,
        }

    return None


@router.get("")
def get_transactions(current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT l.id, l.transaction_id, l.amount_minor, l.currency, l.created_at,
                   t.type, t.status, t.description,
                   a.account_number, a.iban_virtual AS account_iban,

                   tr.beneficiary_name AS tr_beneficiary_name,
                   tr.to_iban          AS tr_to_iban,
                   tr.fee_minor        AS tr_fee_minor,
                   tr.fx_rate          AS tr_fx_rate,
                   tr.source_amount_minor AS tr_source_amount_minor,
                   tr.source_currency  AS tr_source_currency,
                   tr.dest_amount_minor AS tr_dest_amount_minor,
                   tr.dest_currency    AS tr_dest_currency,

                   fa.account_number AS from_account_number,
                   fa.iban_virtual   AS from_iban,
                   fu.nome           AS from_owner_name,
                   ta.account_number AS to_account_number,
                   ta.iban_virtual   AS to_iban_virtual,
                   tu.nome           AS to_owner_name,

                   d.method          AS dep_method,
                   d.reference_code  AS dep_reference_code,
                   d.entidade_code   AS dep_entidade_code,
                   d.phone_number    AS dep_phone_number
            FROM ledger_entries l
            JOIN transactions t ON l.transaction_id = t.id
            JOIN accounts a ON l.account_id = a.id
            LEFT JOIN transfers tr ON tr.transaction_id = t.id
            LEFT JOIN accounts fa  ON fa.id = tr.from_account_id
            LEFT JOIN users    fu  ON fu.id = fa.user_id
            LEFT JOIN accounts ta  ON ta.id = tr.to_account_id
            LEFT JOIN users    tu  ON tu.id = ta.user_id
            LEFT JOIN deposits d   ON d.transaction_id = t.id
            WHERE a.user_id = ?
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT 500
            """,
            (current_user["id"],)
        ).fetchall()

        result = []
        for r in rows:
            has_transfer = r["tr_source_amount_minor"] is not None
            result.append({
                "id": r["id"],
                "transaction_id": r["transaction_id"],
                "amount_minor": r["amount_minor"],
                "amount_decimal": r["amount_minor"] / 100.0,
                "currency": r["currency"],
                "type": r["type"],
                "status": r["status"],
                "description": r["description"],
                "account_number": r["account_number"],
                "account_iban": r["account_iban"],
                "created_at": r["created_at"],
                "counterparty": _counterparty(r),
                "transfer": {
                    "fee_decimal": (r["tr_fee_minor"] or 0) / 100.0,
                    "fx_rate": r["tr_fx_rate"],
                    "source_amount_decimal": r["tr_source_amount_minor"] / 100.0,
                    "source_currency": r["tr_source_currency"],
                    "dest_amount_decimal": r["tr_dest_amount_minor"] / 100.0,
                    "dest_currency": r["tr_dest_currency"],
                } if has_transfer else None,
            })
        return result
