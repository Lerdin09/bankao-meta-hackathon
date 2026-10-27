"""
Provedores de Depósito Angolano (Simulados para o Hackathon).
- Multicaixa Express: Notificação móvel e aprovação no telemóvel.
- Pagamento por Referência: Entidade (ex: 00123) + Referência de 9 dígitos para ATM / Internet Banking.
"""
import uuid
import random
import datetime
from typing import Dict, Any
from app.db import transaction_scope, get_connection

ENTIDADE_PADRAO = "00543"  # Entidade simulada do Bankão

class DepositProvider:
    @staticmethod
    def criar_deposito_referencia(account_id: str, amount_minor: int, currency: str = "AOA") -> Dict[str, Any]:
        """Gera uma referência Multicaixa de 9 dígitos válida por 24 horas."""
        if amount_minor <= 0:
            raise ValueError("Montante inválido.")
            
        deposit_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        # Referência de 9 dígitos em 3 blocos (ex: 123 456 789)
        ref_code = f"{random.randint(100, 999)} {random.randint(100, 999)} {random.randint(100, 999)}"
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        
        with transaction_scope() as conn:
            # Transação inicial pendente
            conn.execute(
                """
                INSERT INTO transactions (id, type, status, description)
                VALUES (?, 'deposit', 'pending', ?)
                """,
                (tx_id, f"Depósito por Referência Multicaixa ({ref_code})")
            )
            # Depósito pendente
            conn.execute(
                """
                INSERT INTO deposits (
                    id, transaction_id, account_id, method, amount_minor, currency,
                    reference_code, entidade_code, status, expires_at
                ) VALUES (?, ?, ?, 'referencia', ?, ?, ?, ?, 'pending', ?)
                """,
                (deposit_id, tx_id, account_id, amount_minor, currency, ref_code, ENTIDADE_PADRAO, expires_at)
            )
            
        return {
            "deposit_id": deposit_id,
            "method": "referencia",
            "entidade": ENTIDADE_PADRAO,
            "referencia": ref_code,
            "amount_minor": amount_minor,
            "amount_decimal": amount_minor / 100.0,
            "currency": currency,
            "expires_at": expires_at.isoformat(),
            "status": "pending"
        }

    @staticmethod
    def criar_deposito_multicaixa_express(account_id: str, amount_minor: int, phone_number: str, currency: str = "AOA") -> Dict[str, Any]:
        """Inicia um pedido de autorização para o telemóvel no Multicaixa Express."""
        if amount_minor <= 0:
            raise ValueError("Montante inválido.")
        if not phone_number or len(phone_number.replace(" ", "")) < 9:
            raise ValueError("Número de telemóvel de Angola inválido.")

        deposit_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)

        with transaction_scope() as conn:
            conn.execute(
                """
                INSERT INTO transactions (id, type, status, description)
                VALUES (?, 'deposit', 'pending', ?)
                """,
                (tx_id, f"Depósito Multicaixa Express ({phone_number})")
            )
            conn.execute(
                """
                INSERT INTO deposits (
                    id, transaction_id, account_id, method, amount_minor, currency,
                    phone_number, status, expires_at
                ) VALUES (?, ?, ?, 'multicaixa_express', ?, ?, ?, 'pending', ?)
                """,
                (deposit_id, tx_id, account_id, amount_minor, currency, phone_number, expires_at)
            )

        return {
            "deposit_id": deposit_id,
            "method": "multicaixa_express",
            "phone_number": phone_number,
            "amount_minor": amount_minor,
            "amount_decimal": amount_minor / 100.0,
            "currency": currency,
            "expires_at": expires_at.isoformat(),
            "status": "pending",
            "message": "Notificação push simulada enviada para o aplicativo Multicaixa Express."
        }
