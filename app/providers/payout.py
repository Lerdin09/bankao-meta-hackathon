"""
Provedor de Payout Internacional e Transferência via IBAN (Simulado).
Simula o envio para a rede SEPA (ex: Portugal/Espanha) ou bancos internacionais.
"""
import uuid
from typing import Dict, Any
from app.iban import iban_valido
from app.providers.fx import FXProvider
from app.ledger import get_account_balance, InsufficientFundsError
from app.db import transaction_scope

class PayoutProvider:
    @staticmethod
    def transferir_para_iban(
        from_account_id: str,
        to_iban: str,
        beneficiary_name: str,
        amount_minor: int,
        source_currency: str,
        dest_currency: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """
        Executa transferência para IBAN com validação Mod 97, débito no livro-razão e cotação FX.
        """
        if amount_minor <= 0:
            raise ValueError("O montante deve ser maior que zero.")

        clean_iban = to_iban.replace(" ", "").upper()
        if not iban_valido(clean_iban):
            raise ValueError(f"IBAN inválido conforme algoritmo Mod 97: {to_iban}")

        if not beneficiary_name or len(beneficiary_name.strip()) < 3:
            raise ValueError("O nome do beneficiário é obrigatório.")

        # Calcular cotação e taxas
        quote = FXProvider.get_quote(source_currency, dest_currency, amount_minor)
        fee_minor = quote["fee_minor"]
        dest_amount_minor = quote["dest_amount_minor"]
        rate = quote["rate"]

        with transaction_scope() as conn:
            # Idempotência
            existing = conn.execute(
                "SELECT id, status FROM transactions WHERE idempotency_key = ?",
                (idempotency_key,)
            ).fetchone()
            if existing:
                return {"transaction_id": existing["id"], "status": existing["status"], "idempotent": True}

            # Validar saldo disponível
            current_balance = get_account_balance(from_account_id, conn)
            if current_balance < amount_minor:
                raise InsufficientFundsError(
                    f"Saldo insuficiente ({current_balance / 100:.2f} {source_currency}) para cobrir o total de {amount_minor / 100:.2f} {source_currency}."
                )

            # Criar transação
            tx_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO transactions (id, type, status, idempotency_key, description)
                VALUES (?, 'transfer_iban', 'completed', ?, ?)
                """,
                (tx_id, idempotency_key, f"Envio internacional para {beneficiary_name} ({clean_iban[:4]}...{clean_iban[-4:]})")
            )

            # Débito no Livro-Razão da conta de origem
            conn.execute(
                """
                INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency)
                VALUES (?, ?, ?, ?)
                """,
                (tx_id, from_account_id, -amount_minor, source_currency)
            )

            # Registro detalhado da transferência
            transfer_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO transfers (
                    id, transaction_id, from_account_id, to_account_id, to_iban,
                    beneficiary_name, source_amount_minor, source_currency,
                    dest_amount_minor, dest_currency, fx_rate, fee_minor, status
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')
                """,
                (
                    transfer_id, tx_id, from_account_id, clean_iban, beneficiary_name,
                    amount_minor, source_currency, dest_amount_minor, dest_currency,
                    rate, fee_minor
                )
            )

        return {
            "transaction_id": tx_id,
            "transfer_id": transfer_id,
            "status": "completed",
            "to_iban": clean_iban,
            "beneficiary_name": beneficiary_name,
            "source_amount_decimal": amount_minor / 100.0,
            "source_currency": source_currency,
            "dest_amount_decimal": dest_amount_minor / 100.0,
            "dest_currency": dest_currency,
            "fx_rate": rate,
            "fee_decimal": fee_minor / 100.0,
            "network": "SEPA Instant / SWIFT Simulator",
            "message": "Transferência internacional processada com sucesso no ambiente sandbox."
        }
