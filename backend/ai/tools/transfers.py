"""
Ferramentas de Transferências, Cotações e Comissões para a IA do BankAO.
Gera cotações, valida saldos e prepara propostas seguras com confirmação explícita.
NUNCA movimenta dinheiro diretamente pela IA.
"""
from typing import Any, Dict, List, Optional

from backend.database import get_connection
from backend.ai.intents import find_iban
from backend.services.iban import iban_valido
from backend.services.ledger import get_user_accounts


FEE_INTERNAL_PCT = 1.0
FEE_IBAN_PCT = 2.5


def tool_get_transfer_fees_info(amount: float = 10000.0, currency: str = "AOA") -> Dict[str, Any]:
    """
    Informa e calcula detalhadamente as taxas e comissões do BankAO.
    Responde à pergunta: 'Quanto pago de comissões se enviar dinheiro?'
    """
    amount = max(0.0, float(amount))
    fee_internal = round(amount * (FEE_INTERNAL_PCT / 100.0), 2)
    fee_iban = round(amount * (FEE_IBAN_PCT / 100.0), 2)

    return {
        "amount_example": amount,
        "currency": currency,
        "internal_transfer": {
            "fee_percent": FEE_INTERNAL_PCT,
            "fee_amount": fee_internal,
            "net_received": round(amount - fee_internal, 2),
            "description": "Entre contas BankAO (por número de conta ou e-mail). Liquidação imediata."
        },
        "iban_transfer": {
            "fee_percent": FEE_IBAN_PCT,
            "fee_amount": fee_iban,
            "net_received": round(amount - fee_iban, 2),
            "description": "Para qualquer banco em Angola (BNA/EMIS) ou internacional (Portugal/SEPA via EUR)."
        }
    }


def tool_quote_transfer(
    user_id: str,
    destination: str,
    amount: float,
    currency: str = "AOA",
    beneficiary_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Prepara a cotação e validação de uma transferência bancária.
    Verifica se a conta tem saldo suficiente e calcula taxas oficiais.
    Retorna uma proposta com 'requires_confirmation: True'.
    """
    amount = float(amount)
    if amount <= 0:
        return {"error": "O montante deve ser estritamente superior a zero."}

    user_accs = get_user_accounts(user_id)
    acc = next((a for a in user_accs if a["currency"] == currency), None)
    if not acc:
        return {"error": f"Não possui conta ativa em {currency}."}

    available_bal = acc["balance_decimal"]
    dest_clean = destination.strip().replace(" ", "").upper()

    # Detectar tipo de transferência
    # IBAN = letras do país + dígitos de controlo (AO06...). Um nº de conta BankAO (só dígitos) nunca é IBAN.
    iban_hit = find_iban(dest_clean)
    is_iban = bool(iban_hit and iban_hit[0] == dest_clean)
    fee_pct = FEE_IBAN_PCT if is_iban else FEE_INTERNAL_PCT
    fee_amount = round(amount * (fee_pct / 100.0), 2)
    net_amount = round(amount - fee_amount, 2)

    has_balance = available_bal >= amount

    # Destinatário interno vs IBAN
    transfer_type = "TRANSFER_IBAN" if is_iban else "TRANSFER_INTERNAL"
    action_data = {
        "type": transfer_type,
        "amount": amount,
        "fee_amount": fee_amount,
        "net_amount": net_amount,
        "currency": currency,
        "from_account_id": acc["id"],
        "from_account_number": acc["account_number"],
        "beneficiary_name": beneficiary_name or destination,
    }

    if is_iban:
        action_data["to_iban"] = dest_clean
        action_data["iban_valid"] = iban_valido(dest_clean)
    else:
        if "@" in destination:
            action_data["to_email"] = destination.strip()
        else:
            action_data["to_account_number"] = dest_clean

    return {
        "valid": True,
        "destination": destination,
        "is_iban": is_iban,
        "amount": amount,
        "fee_amount": fee_amount,
        "fee_percent": fee_pct,
        "net_amount": net_amount,
        "currency": currency,
        "available_balance": available_bal,
        "has_sufficient_funds": has_balance,
        "requires_confirmation": True,
        "action": action_data
    }
