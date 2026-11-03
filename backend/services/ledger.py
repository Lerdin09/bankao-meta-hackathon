"""
Motor de Livro-Razão (Double-Entry Ledger) do BankAO.
Garante consistência matemática:
- Nenhuma conta fica com saldo negativo.
- Valores sempre em inteiros mínimos (cêntimos / minor units).
- Idempotência em todas as operações.
"""
import uuid
import sqlite3
from typing import Optional, Dict, Any, List
from backend.database import transaction_scope, get_connection

class InsufficientFundsError(Exception):
    pass

class IdempotencyDuplicateError(Exception):
    pass

class AccountNotFoundError(Exception):
    pass

def get_account_balance(account_id: str, conn: Optional[sqlite3.Connection] = None) -> int:
    """Retorna o saldo em minor units (cêntimos) da conta indicada."""
    query = "SELECT COALESCE(SUM(amount_minor), 0) as balance FROM ledger_entries WHERE account_id = ?"
    if conn:
        row = conn.execute(query, (account_id,)).fetchone()
        return int(row["balance"])
    else:
        with get_connection() as c:
            row = c.execute(query, (account_id,)).fetchone()
            return int(row["balance"])

def get_user_accounts(user_id: str) -> List[Dict[str, Any]]:
    """Retorna todas as carteiras do utilizador com saldo calculado em tempo real."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.user_id, a.account_number, a.iban_virtual, a.currency, a.status,
                   COALESCE(SUM(l.amount_minor), 0) as balance_minor
            FROM accounts a
            LEFT JOIN ledger_entries l ON a.id = l.account_id
            WHERE a.user_id = ?
            GROUP BY a.id
            ORDER BY a.currency ASC
            """,
            (user_id,)
        ).fetchall()
        
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "account_number": r["account_number"],
                "iban_virtual": r["iban_virtual"],
                "currency": r["currency"],
                "status": r["status"],
                "balance_minor": r["balance_minor"],
                "balance_decimal": r["balance_minor"] / 100.0,
            }
            for r in rows
        ]

def execute_internal_transfer(
    from_account_id: str,
    to_account_id: str,
    amount_minor: int,
    idempotency_key: str,
    description: str = "Transferência interna BankAO",
    fee_minor: int = 0,
    beneficiary_name: str = "Transferência Interna",
) -> Dict[str, Any]:
    """
    Executa uma transferência atômica entre duas contas internas da mesma moeda.
    """
    if amount_minor <= 0:
        raise ValueError("O montante deve ser estritamente positivo.")
    if from_account_id == to_account_id:
        raise ValueError("Conta de origem e destino não podem ser iguais.")

    dest_amount_minor = max(0, amount_minor - fee_minor)

    with transaction_scope() as conn:
        # Checagem de idempotência
        existing = conn.execute(
            "SELECT id, status FROM transactions WHERE idempotency_key = ?",
            (idempotency_key,)
        ).fetchone()
        if existing:
            return {"transaction_id": existing["id"], "status": existing["status"], "idempotent": True}

        # Obter contas e moedas
        from_acc = conn.execute("SELECT id, currency, status FROM accounts WHERE id = ?", (from_account_id,)).fetchone()
        to_acc = conn.execute("SELECT id, currency, status FROM accounts WHERE id = ?", (to_account_id,)).fetchone()

        if not from_acc or not to_acc:
            raise AccountNotFoundError("Uma das contas envolvidas não foi encontrada.")
        if from_acc["status"] != "active" or to_acc["status"] != "active":
            raise ValueError("Uma das contas está inativa ou bloqueada.")
        if from_acc["currency"] != to_acc["currency"]:
            raise ValueError("Transferência interna direta requer contas com a mesma moeda.")

        currency = from_acc["currency"]

        # Verificar saldo
        current_balance = get_account_balance(from_account_id, conn)
        if current_balance < amount_minor:
            raise InsufficientFundsError(
                f"Saldo insuficiente ({current_balance / 100:.2f} {currency}) para debitar {amount_minor / 100:.2f} {currency}."
            )

        # Criar transação
        tx_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO transactions (id, type, status, idempotency_key, description)
            VALUES (?, 'transfer_internal', 'completed', ?, ?)
            """,
            (tx_id, idempotency_key, description)
        )

        # Lançamento de Dupla Entrada no Livro-Razão
        # 1. Débito na conta remetente (valor total enviado)
        conn.execute(
            """
            INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency)
            VALUES (?, ?, ?, ?)
            """,
            (tx_id, from_account_id, -amount_minor, currency)
        )
        # 2. Crédito na conta destinatária (valor líquido após taxa)
        conn.execute(
            """
            INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency)
            VALUES (?, ?, ?, ?)
            """,
            (tx_id, to_account_id, dest_amount_minor, currency)
        )

        # Registo do detalhe da transferência
        transfer_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO transfers (
                id, transaction_id, from_account_id, to_account_id, beneficiary_name,
                source_amount_minor, source_currency, dest_amount_minor, dest_currency,
                fx_rate, fee_minor, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, 'completed')
            """,
            (transfer_id, tx_id, from_account_id, to_account_id, beneficiary_name, amount_minor, currency, dest_amount_minor, currency, fee_minor)
        )

        return {
            "transaction_id": tx_id,
            "status": "completed",
            "amount_minor": amount_minor,
            "currency": currency,
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "fee_minor": fee_minor,
            "dest_amount_minor": dest_amount_minor,
            "beneficiary_name": beneficiary_name
        }

def credit_deposit(
    deposit_id: str,
) -> Dict[str, Any]:
    """
    Confirma um depósito e credita no livro-razão de forma segura e atômica.
    """
    with transaction_scope() as conn:
        deposit = conn.execute(
            "SELECT * FROM deposits WHERE id = ?", (deposit_id,)
        ).fetchone()

        if not deposit:
            raise ValueError("Depósito não encontrado.")
        if deposit["status"] == "completed":
            return {"deposit_id": deposit_id, "status": "completed", "already_processed": True}
        if deposit["status"] != "pending":
            raise ValueError(f"Depósito não pode ser concluído no estado atual: {deposit['status']}")

        tx_id = deposit["transaction_id"]
        account_id = deposit["account_id"]
        amount_minor = deposit["amount_minor"]
        currency = deposit["currency"]

        # Atualiza status do depósito
        conn.execute("UPDATE deposits SET status = 'completed' WHERE id = ?", (deposit_id,))
        conn.execute("UPDATE transactions SET status = 'completed' WHERE id = ?", (tx_id,))

        # Entrada de crédito no Livro-Razão
        conn.execute(
            """
            INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency)
            VALUES (?, ?, ?, ?)
            """,
            (tx_id, account_id, amount_minor, currency)
        )

        return {
            "deposit_id": deposit_id,
            "status": "completed",
            "account_id": account_id,
            "amount_minor": amount_minor,
            "currency": currency
        }


def post_savings_movement(
    conn: sqlite3.Connection,
    account_id: str,
    amount_minor: int,
    idempotency_key: str,
    description: str,
    tx_type: str = "savings_deposit",
) -> Dict[str, Any]:
    """
    Movimento de poupança numa ligação já aberta (faz parte da transação do chamador).
    amount_minor < 0 debita a conta (depósito na meta); > 0 credita (resgate ao apagar a meta).
    Idempotente: a mesma chave nunca debita duas vezes.
    """
    if amount_minor == 0:
        raise ValueError("O montante deve ser diferente de zero.")
    existing = conn.execute(
        "SELECT id FROM transactions WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if existing:
        return {"transaction_id": existing["id"], "idempotent": True}

    acc = conn.execute("SELECT id, currency, status FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not acc:
        raise AccountNotFoundError("Conta não encontrada.")
    if acc["status"] != "active":
        raise ValueError("A conta está inativa ou bloqueada.")

    if amount_minor < 0:
        balance = get_account_balance(account_id, conn)
        if balance < -amount_minor:
            raise InsufficientFundsError(
                f"Saldo insuficiente ({balance / 100:,.2f} {acc['currency']} disponível)."
            )

    tx_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO transactions (id, type, status, idempotency_key, description) VALUES (?, ?, 'completed', ?, ?)",
        (tx_id, tx_type, idempotency_key, description),
    )
    conn.execute(
        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, ?, ?)",
        (tx_id, account_id, amount_minor, acc["currency"]),
    )
    return {"transaction_id": tx_id, "idempotent": False, "currency": acc["currency"]}


def post_investment_movement(
    conn: sqlite3.Connection,
    account_id: str,
    amount_minor: int,
    idempotency_key: str,
    description: str,
    tx_type: str = "investment_apply",
) -> Dict[str, Any]:
    """
    Movimento de investimento no livro-razão:
    amount_minor < 0 debita a conta para subscrição/reforço.
    amount_minor > 0 credita a conta ao resgatar ou receber dividendos/juros.
    """
    if amount_minor == 0:
        raise ValueError("O montante deve ser diferente de zero.")
    existing = conn.execute(
        "SELECT id FROM transactions WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if existing:
        return {"transaction_id": existing["id"], "idempotent": True}

    acc = conn.execute("SELECT id, currency, status FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if not acc:
        raise AccountNotFoundError("Conta não encontrada.")
    if acc["status"] != "active":
        raise ValueError("A conta está inativa ou bloqueada.")

    if amount_minor < 0:
        balance = get_account_balance(account_id, conn)
        if balance < -amount_minor:
            raise InsufficientFundsError(
                f"Saldo insuficiente ({balance / 100:,.2f} {acc['currency']} disponível)."
            )

    tx_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO transactions (id, type, status, idempotency_key, description) VALUES (?, ?, 'completed', ?, ?)",
        (tx_id, tx_type, idempotency_key, description),
    )
    conn.execute(
        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, ?, ?)",
        (tx_id, account_id, amount_minor, acc["currency"]),
    )
    return {"transaction_id": tx_id, "idempotent": False, "currency": acc["currency"]}

