"""
Testes automatizados para transferências multimoeda e cálculo em tempo real de taxas:
- Transferência entre contas (e-mail) com taxa de 1%
- Transferência bancária IBAN com taxa de 2.5%
- Conversões com taxa de câmbio USD -> AOA (1000) e USD -> EUR
- Formato de 2 níveis (moeda enviada no topo e moeda do país embaixo)
"""
import uuid
import pytest
from app.db import init_db, get_connection
from app.iban import gerar_iban_ficticio
from app.providers.fx import FXProvider
from app.providers.payout import PayoutProvider
from app.ledger import execute_internal_transfer, get_account_balance

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_fx_quote_usd_aoa_rates_and_fees():
    """
    Verifica se $100 em USD para AOA gera exatamente:
    - Quantia enviada: 100$ (100.000 KZ)
    - Taxa de 2.5%: 2.5$ (2.500 KZ)
    - Dinheiro que vai chegar: 97.5$ (97.500 KZ)
    """
    amount_minor = 10000 # $100.00 em minor units (cents)
    quote = FXProvider.get_quote("USD", "AOA", amount_minor, custom_fee_pct=0.025)

    assert quote["source_amount_decimal"] == 100.0
    assert quote["fee_decimal"] == 2.5
    assert quote["fee_percentage"] == 2.5
    # 97.5 USD * 1000 = 97.500 Kz
    assert quote["dest_amount_decimal"] == 97500.0
    assert quote["rate"] == 1000.0

def test_internal_transfer_with_one_percent_fee():
    """
    Verifica transferência interna entre contas com taxa de 1%:
    - Envia $100: Taxa = $1.00, Chega = $99.00
    """
    with get_connection() as conn:
        u1 = str(uuid.uuid4())
        u2 = str(uuid.uuid4())
        conn.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'Enviador USD', ?, 'hash')", (u1, f"env_{u1[:8]}@bankao.ao"))
        conn.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'Recetor USD', ?, 'hash')", (u2, f"rec_{u2[:8]}@bankao.ao"))

        acc1 = str(uuid.uuid4())
        acc2 = str(uuid.uuid4())
        conn.execute("INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'USD')", (acc1, u1, f"0060{acc1[:8]}", f"AO069999{acc1[:10]}"))
        conn.execute("INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'USD')", (acc2, u2, f"0060{acc2[:8]}", f"AO069999{acc2[:10]}"))

        # Saldo inicial de $500 (50,000 cents)
        tx_init = str(uuid.uuid4())
        conn.execute("INSERT INTO transactions (id, type, status) VALUES (?, 'deposit', 'completed')", (tx_init,))
        conn.execute("INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, 50000, 'USD')", (tx_init, acc1))

    # Executar transferência de $100 com 1% de taxa ($1.00)
    amount_minor = 10000 # $100.00
    fee_minor = 100      # $1.00 (1%)
    idemp = f"test_int_{uuid.uuid4()}"

    res = execute_internal_transfer(
        from_account_id=acc1,
        to_account_id=acc2,
        amount_minor=amount_minor,
        fee_minor=fee_minor,
        idempotency_key=idemp,
        description="Teste $100 taxa 1%",
        beneficiary_name="Recetor USD"
    )

    assert res["status"] == "completed"

    with get_connection() as conn:
        bal_sender = get_account_balance(acc1, conn)
        bal_receiver = get_account_balance(acc2, conn)

        # Enviador debitado de $100: 50000 - 10000 = 40000 cents ($400)
        assert bal_sender == 40000
        # Recetor creditado de $99: 10000 - 100 = 9900 cents ($99)
        assert bal_receiver == 9900

def test_payout_iban_usd_to_angola_two_point_five_percent():
    """
    Testa PayoutProvider para envio de $100 USD para IBAN de Angola (AO):
    - Débito na conta USD: $100.00
    - Taxa: 2.5% ($2.50)
    - Crédito no destino: 97.500 KZ
    """
    iban_ao = gerar_iban_ficticio("AO")
    with get_connection() as conn:
        u = str(uuid.uuid4())
        conn.execute("INSERT INTO users (id, nome, email, password_hash) VALUES (?, 'Remetente USD', ?, 'hash')", (u, f"remetente_{u[:8]}@bankao.ao"))

        acc_usd = str(uuid.uuid4())
        conn.execute("INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'USD')", (acc_usd, u, f"0060{acc_usd[:8]}", f"AO069999{acc_usd[:10]}"))

        # Saldo inicial de $1,000 (100,000 cents)
        tx_init = str(uuid.uuid4())
        conn.execute("INSERT INTO transactions (id, type, status) VALUES (?, 'deposit', 'completed')", (tx_init,))
        conn.execute("INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, 100000, 'USD')", (tx_init, acc_usd))

    idemp = f"test_iban_{uuid.uuid4()}"
    res = PayoutProvider.transferir_para_iban(
        from_account_id=acc_usd,
        to_iban=iban_ao,
        beneficiary_name="Adul Popo Angol",
        amount_minor=10000, # $100.00
        source_currency="USD",
        dest_currency="AOA",
        idempotency_key=idemp
    )

    assert res["status"] == "completed"
    assert res["source_amount_decimal"] == 100.0
    assert res["fee_decimal"] == 2.5
    assert res["dest_amount_decimal"] == 97500.0 # 97.5 USD * 1000 AOA

    with get_connection() as conn:
        bal = get_account_balance(acc_usd, conn)
        # 100,000 - 10,000 = 90,000 cents ($900.00)
        assert bal == 90000
