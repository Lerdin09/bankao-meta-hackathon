"""
Suíte de testes automatizados do Bankão:
- Validação de IBAN Mod 97 (AO e PT)
- Transações atômicas no livro-razão
- Bloqueio estrito de saldo negativo
- Idempotência
"""
import pytest
import uuid
from app.iban import iban_valido, gerar_iban_ficticio
from app.db import init_db, get_connection
from app.ledger import (
    execute_internal_transfer,
    get_account_balance,
    InsufficientFundsError
)

@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()

def test_iban_validation_and_generation():
    # Gerar IBAN fictício válido para Angola
    iban_ao = gerar_iban_ficticio("AO")
    assert iban_ao.startswith("AO")
    assert len(iban_ao) == 25
    assert iban_valido(iban_ao) is True

    # Gerar IBAN fictício válido para Portugal
    iban_pt = gerar_iban_ficticio("PT")
    assert iban_pt.startswith("PT")
    assert len(iban_pt) == 25
    assert iban_valido(iban_pt) is True

    # Teste de IBAN corrompido / inválido
    corrupted = iban_pt[:-1] + ("1" if iban_pt[-1] != "1" else "2")
    assert iban_valido(corrupted) is False
    assert iban_valido("AO06123456789") is False

def test_ledger_double_entry_and_negative_balance_block():
    with get_connection() as conn:
        u1_id = str(uuid.uuid4())
        u2_id = str(uuid.uuid4())
        conn.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'User 1', 'u1@test.com', 'hash')", (u1_id,))
        conn.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'User 2', 'u2@test.com', 'hash')", (u2_id,))

        acc1_id = str(uuid.uuid4())
        acc2_id = str(uuid.uuid4())
        conn.execute("INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, 'ACC1', 'IBAN1', 'AOA')", (acc1_id, u1_id))
        conn.execute("INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, 'ACC2', 'IBAN2', 'AOA')", (acc2_id, u2_id))

        # Creditar 50.000 Kz (5.000.000 minor units) na acc1
        tx_init = str(uuid.uuid4())
        conn.execute("INSERT INTO transactions (id, type, status) VALUES (?, 'deposit', 'completed')", (tx_init,))
        conn.execute("INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, 5000000, 'AOA')", (tx_init, acc1_id))

    # Teste 1: Transferir 20.000 Kz (2.000.000 minor units) com sucesso
    res = execute_internal_transfer(
        from_account_id=acc1_id,
        to_account_id=acc2_id,
        amount_minor=2000000,
        idempotency_key="idemp_test_1"
    )
    assert res["status"] == "completed"

    # Verificar saldos
    assert get_account_balance(acc1_id) == 3000000  # 30.000 Kz
    assert get_account_balance(acc2_id) == 2000000  # 20.000 Kz

    # Teste 2: Idempotência (repetir a mesma requisição não deve debitar duas vezes)
    res_repeat = execute_internal_transfer(
        from_account_id=acc1_id,
        to_account_id=acc2_id,
        amount_minor=2000000,
        idempotency_key="idemp_test_1"
    )
    assert res_repeat.get("idempotent") is True
    assert get_account_balance(acc1_id) == 3000000  # Mantém 30.000 Kz

    # Teste 3: Tentar transferir mais do que o saldo disponível (deve falhar e não alterar saldos)
    with pytest.raises(InsufficientFundsError):
        execute_internal_transfer(
            from_account_id=acc1_id,
            to_account_id=acc2_id,
            amount_minor=99999999,
            idempotency_key="idemp_test_overflow"
        )
    assert get_account_balance(acc1_id) == 3000000
