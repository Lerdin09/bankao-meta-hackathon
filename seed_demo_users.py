"""
Seed de 2 utilizadores demo com histórico realista desde Agosto 2026.

Utilizador 1 — Ana Luísa Ferreira (Professora, Luanda)
  • Salário mensal ~250.000 Kz
  • Despesas variadas: alimentação, transporte, educação, lazer
  • Meta de poupança: Viagem a Lisboa
  • 1 Depósito a Prazo

Utilizador 2 — João Pedro Makiesse (Engenheiro, Luanda)
  • Salário mensal ~400.000 Kz
  • Despesas: combustível, restaurantes, telecomunicações, investimentos
  • Meta: Comprar carro
  • 1 investimento BODIVA + Depósito a Prazo

Executar a partir da raiz do projecto:
    python seed_demo_users.py
"""

import sys, os, uuid, random, datetime
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import get_connection, init_db
from backend.core.security import get_password_hash
from backend.services.iban import gerar_iban_ficticio

# ── Garantir que as tabelas existem ──────────────────────────────────────────
init_db()

TODAY = datetime.date(2026, 11, 2)
PASSWORD_HASH = get_password_hash("Demo1234!")

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def date_range(start: datetime.date, end: datetime.date):
    d = start
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)

def kz(value: float) -> int:
    """Converte Kz para minor units (cêntimos)."""
    return int(round(value * 100))

def make_id() -> str:
    return str(uuid.uuid4())

def insert_deposit_ledger(conn, user_id: str, acc_id: str, amount_kz: float, date: datetime.date, desc: str):
    """Cria depósito + ledger entry."""
    tx_id = make_id()
    dt = datetime.datetime.combine(date, datetime.time(random.randint(7, 19), random.randint(0, 59)))
    conn.execute(
        "INSERT INTO transactions (id, type, status, description, created_at) VALUES (?,?,?,?,?)",
        (tx_id, "deposit", "completed", desc, dt.isoformat())
    )
    dep_id = make_id()
    conn.execute(
        "INSERT INTO deposits (id, transaction_id, account_id, method, amount_minor, currency, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (dep_id, tx_id, acc_id, "multicaixa_express", kz(amount_kz), "AOA", "completed", dt.isoformat())
    )
    conn.execute(
        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at) VALUES (?,?,?,?,?)",
        (tx_id, acc_id, kz(amount_kz), "AOA", dt.isoformat())
    )

def insert_expense(conn, user_id: str, name: str, category: str, amount_kz: float, date: datetime.date, notes: str = ""):
    conn.execute(
        "INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, notes) VALUES (?,?,?,?,?,?,?,?,?)",
        (make_id(), user_id, name, category, kz(amount_kz), "AOA", date.isoformat(), "manual", notes)
    )

def insert_transfer_out(conn, acc_id: str, beneficiary: str, amount_kz: float, date: datetime.date, desc: str):
    """Transferência de saída (débito na conta)."""
    tx_id = make_id()
    dt = datetime.datetime.combine(date, datetime.time(random.randint(9, 17), random.randint(0, 59)))
    conn.execute(
        "INSERT INTO transactions (id, type, status, description, created_at) VALUES (?,?,?,?,?)",
        (tx_id, "transfer_iban", "completed", desc, dt.isoformat())
    )
    tf_id = make_id()
    dest_iban = gerar_iban_ficticio("AO")
    conn.execute(
        """INSERT INTO transfers
           (id, transaction_id, from_account_id, to_iban, beneficiary_name,
            source_amount_minor, source_currency, dest_amount_minor, dest_currency, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (tf_id, tx_id, acc_id, dest_iban, beneficiary,
         kz(amount_kz), "AOA", kz(amount_kz), "AOA", "completed", dt.isoformat())
    )
    conn.execute(
        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at) VALUES (?,?,?,?,?)",
        (tx_id, acc_id, -kz(amount_kz), "AOA", dt.isoformat())
    )

def insert_savings_goal(conn, user_id: str, acc_id: str, name: str, target_kz: float,
                        monthly_kz: float, start_date: datetime.date, icon: str, deadline: str) -> str:
    goal_id = make_id()
    # Calcular quanto foi poupado até hoje
    months_passed = max(0, (TODAY.year - start_date.year) * 12 + (TODAY.month - start_date.month))
    saved_kz = min(monthly_kz * months_passed, target_kz)
    status = "completed" if saved_kz >= target_kz else "on-track"
    conn.execute(
        """INSERT INTO savings_goals
           (id, user_id, name, target_minor, saved_minor, monthly_minor, deadline, icon_key, status, currency, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (goal_id, user_id, name, kz(target_kz), kz(saved_kz), kz(monthly_kz),
         deadline, icon, status, "AOA", start_date.isoformat())
    )
    # Criar ledger entries mensais para as contribuições
    for i in range(months_passed):
        contrib_date = start_date + datetime.timedelta(days=30 * i)
        if contrib_date > TODAY:
            break
        tx_id = make_id()
        dt = datetime.datetime.combine(contrib_date, datetime.time(10, 0))
        conn.execute(
            "INSERT INTO transactions (id, type, status, description, created_at) VALUES (?,?,?,?,?)",
            (tx_id, "savings_auto_debit", "completed", f"Débito automático — {name}", dt.isoformat())
        )
        conn.execute(
            "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at) VALUES (?,?,?,?,?)",
            (tx_id, acc_id, -kz(monthly_kz), "AOA", dt.isoformat())
        )
        conn.execute(
            "INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, goal_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (make_id(), user_id, f"Poupança — {name}", "Poupança", kz(monthly_kz), "AOA", contrib_date.isoformat(), "savings", goal_id)
        )
    return goal_id

def insert_investment(conn, user_id: str, acc_id: str, name: str, category: str,
                      amount_kz: float, rate: float, start_date: datetime.date,
                      term_months: int = 12, currency: str = "AOA"):
    inv_id = make_id()
    months = (TODAY.year - start_date.year) * 12 + (TODAY.month - start_date.month)
    monthly_rate = rate / 100 / 12
    current_value = amount_kz * ((1 + monthly_rate) ** months)
    yield_val = current_value - amount_kz
    maturity = start_date + datetime.timedelta(days=30 * term_months)
    conn.execute(
        """INSERT INTO user_investments
           (id, user_id, name, category, institution, is_external, account_id,
            amount_invested_minor, current_value_minor, accumulated_yield_minor,
            currency, rate_annual, start_date, maturity_date, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (inv_id, user_id, name, category, "BankAO", 0, acc_id,
         kz(amount_kz), kz(current_value), kz(yield_val),
         currency, rate, start_date.isoformat(), maturity.isoformat(),
         "ativo", start_date.isoformat())
    )
    # Débito do valor investido na conta
    tx_id = make_id()
    dt = datetime.datetime.combine(start_date, datetime.time(11, 0))
    conn.execute(
        "INSERT INTO transactions (id, type, status, description, created_at) VALUES (?,?,?,?,?)",
        (tx_id, "investment", "completed", f"Investimento — {name}", dt.isoformat())
    )
    conn.execute(
        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at) VALUES (?,?,?,?,?)",
        (tx_id, acc_id, -kz(amount_kz), currency, dt.isoformat())
    )

def create_user(conn, email: str, nome: str, primeiro_nome: str, ultimo_nome: str,
                telefone: str) -> str:
    user_id = make_id()
    conn.execute(
        """INSERT OR IGNORE INTO users
           (id, nome, primeiro_nome, ultimo_nome, email, password_hash, telefone, kyc_status, terms_accepted)
           VALUES (?,?,?,?,?,?,?,'verificado',1)""",
        (user_id, nome, primeiro_nome, ultimo_nome, email, PASSWORD_HASH, telefone)
    )
    # Verificar se já existia
    existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    return existing["id"] if existing else user_id

def create_accounts(conn, user_id: str):
    accounts = {}
    for currency, prefix, country in [("AOA", "0040", "AO"), ("EUR", "0050", "PT"), ("USD", "0060", "US")]:
        existing = conn.execute(
            "SELECT id FROM accounts WHERE user_id=? AND currency=?", (user_id, currency)
        ).fetchone()
        if existing:
            accounts[currency] = existing["id"]
        else:
            acc_id = make_id()
            acc_num = f"{prefix}{random.randint(10000000, 99999999)}"
            iban = gerar_iban_ficticio(country)
            conn.execute(
                "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?,?,?,?,?)",
                (acc_id, user_id, acc_num, iban, currency)
            )
            accounts[currency] = acc_id
    return accounts

def insert_contact(conn, user_id: str, name: str, iban: str, nickname: str = ""):
    ref_key = f"i:{iban}"
    conn.execute(
        """INSERT OR IGNORE INTO contacts (id, user_id, kind, ref_key, name, nickname, iban, favorite)
           VALUES (?,?,?,?,?,?,?,?)""",
        (make_id(), user_id, "iban", ref_key, name, nickname, iban, 1 if nickname else 0)
    )

def insert_memory(conn, user_id: str, key: str, value: str):
    conn.execute(
        """INSERT INTO copilot_memory (id, user_id, memory_key, memory_value)
           VALUES (?,?,?,?)
           ON CONFLICT(user_id, memory_key) DO UPDATE SET memory_value=excluded.memory_value""",
        (make_id(), user_id, key, value)
    )


# =============================================================================
# UTILIZADOR 1 — Ana Luísa Ferreira | Professora | Luanda
# =============================================================================

def seed_ana(conn):
    print("\n[1/2] A criar Ana Luisa Ferreira...")

    user_id = create_user(
        conn,
        email="ana.ferreira@bankao.ao",
        nome="Ana Luísa Ferreira",
        primeiro_nome="Ana Luísa",
        ultimo_nome="Ferreira",
        telefone="+244924111222"
    )
    accs = create_accounts(conn, user_id)
    aoa_id = accs["AOA"]

    # ── Memória do Copilot ────────────────────────────────────────────────────
    insert_memory(conn, user_id, "nome_preferido", "Ana")
    insert_memory(conn, user_id, "rendimento_mensal", "250.000 Kz")
    insert_memory(conn, user_id, "rendimento_mensal_numerico", "250000")
    insert_memory(conn, user_id, "perfil_risco", "Conservador (foco em capital 100% garantido)")
    insert_memory(conn, user_id, "interesse_viagem", "Meta/Gosto: Viagem a Lisboa em 2027")
    insert_memory(conn, user_id, "interesse_estudos", "Meta/Gosto: Mestrado em Educação")
    insert_memory(conn, user_id, "habito_poupanca", "Poupa mensalmente de forma disciplinada")

    # ── Contactos frequentes ──────────────────────────────────────────────────
    insert_contact(conn, user_id, "Mãe — Conceição Ferreira", gerar_iban_ficticio("AO"), "Mãe")
    insert_contact(conn, user_id, "Renda Casa", gerar_iban_ficticio("AO"), "Senhorio")
    insert_contact(conn, user_id, "Escola João de Deus", gerar_iban_ficticio("AO"), "Propinas")

    # ── Salários mensais (crédito no início de cada mês) ─────────────────────
    MONTHS = [
        datetime.date(2026, 8, 5),
        datetime.date(2026, 9, 5),
        datetime.date(2026, 10, 5),
        datetime.date(2026, 11, 3),  # este mês ainda não chegou inteiro
    ]
    for d in MONTHS:
        insert_deposit_ledger(conn, user_id, aoa_id, 250000, d, "Salário — MINEDH")

    # Depósito inicial (saldo de arranque em Agosto)
    insert_deposit_ledger(conn, user_id, aoa_id, 85000, datetime.date(2026, 8, 1), "Saldo anterior transferido")

    # ── Despesas mês a mês ────────────────────────────────────────────────────

    # AGOSTO 2026
    insert_expense(conn, user_id, "Renda do apartamento", "Habitação", 65000, datetime.date(2026, 8, 1))
    insert_expense(conn, user_id, "Supermercado Nosso Super", "Alimentação", 28400, datetime.date(2026, 8, 3))
    insert_expense(conn, user_id, "Propina — Escola Filha", "Educação", 15000, datetime.date(2026, 8, 4))
    insert_expense(conn, user_id, "Candongueiro + Táxi semana", "Transporte", 8200, datetime.date(2026, 8, 7))
    insert_expense(conn, user_id, "Unitel recarga", "Telecomunicações", 5000, datetime.date(2026, 8, 9))
    insert_expense(conn, user_id, "Restaurante Girassol", "Restaurantes", 9800, datetime.date(2026, 8, 12))
    insert_expense(conn, user_id, "Farmácia Bem-Estar", "Saúde", 6300, datetime.date(2026, 8, 15))
    insert_expense(conn, user_id, "Supermercado Kero", "Alimentação", 19700, datetime.date(2026, 8, 18))
    insert_expense(conn, user_id, "Netflix + Dstv", "Lazer", 7500, datetime.date(2026, 8, 20))
    insert_expense(conn, user_id, "Roupa — Shopping Belas", "Vestuário", 22000, datetime.date(2026, 8, 22))
    insert_expense(conn, user_id, "Electricidade ENDE", "Habitação", 4800, datetime.date(2026, 8, 25))
    insert_expense(conn, user_id, "Combustível carro", "Transporte", 12000, datetime.date(2026, 8, 27))
    insert_transfer_out(conn, aoa_id, "Conceição Ferreira (Mãe)", 20000, datetime.date(2026, 8, 28), "Ajuda familiar mensal")

    # SETEMBRO 2026
    insert_expense(conn, user_id, "Renda do apartamento", "Habitação", 65000, datetime.date(2026, 9, 1))
    insert_expense(conn, user_id, "Supermercado Nosso Super", "Alimentação", 31200, datetime.date(2026, 9, 4))
    insert_expense(conn, user_id, "Propina — Escola Filha", "Educação", 15000, datetime.date(2026, 9, 5))
    insert_expense(conn, user_id, "Candongueiro + Táxi", "Transporte", 7600, datetime.date(2026, 9, 8))
    insert_expense(conn, user_id, "Unitel — plano internet", "Telecomunicações", 8500, datetime.date(2026, 9, 10))
    insert_expense(conn, user_id, "Almoço colegas escola", "Restaurantes", 6400, datetime.date(2026, 9, 13))
    insert_expense(conn, user_id, "Consulta médica + análises", "Saúde", 18500, datetime.date(2026, 9, 16))
    insert_expense(conn, user_id, "Supermercado Kero", "Alimentação", 24100, datetime.date(2026, 9, 19))
    insert_expense(conn, user_id, "Livros escolares", "Educação", 11200, datetime.date(2026, 9, 21))
    insert_expense(conn, user_id, "Electricidade ENDE", "Habitação", 5100, datetime.date(2026, 9, 24))
    insert_expense(conn, user_id, "Combustível", "Transporte", 13500, datetime.date(2026, 9, 26))
    insert_expense(conn, user_id, "Jantar aniversário", "Restaurantes", 14000, datetime.date(2026, 9, 28))
    insert_transfer_out(conn, aoa_id, "Conceição Ferreira (Mãe)", 20000, datetime.date(2026, 9, 29), "Ajuda familiar mensal")

    # OUTUBRO 2026
    insert_expense(conn, user_id, "Renda do apartamento", "Habitação", 65000, datetime.date(2026, 10, 1))
    insert_expense(conn, user_id, "Supermercado Nosso Super", "Alimentação", 27800, datetime.date(2026, 10, 3))
    insert_expense(conn, user_id, "Propina — Escola Filha", "Educação", 15000, datetime.date(2026, 10, 4))
    insert_expense(conn, user_id, "Unitel recarga", "Telecomunicações", 5000, datetime.date(2026, 10, 7))
    insert_expense(conn, user_id, "Candongueiro + Táxi", "Transporte", 9100, datetime.date(2026, 10, 9))
    insert_expense(conn, user_id, "Restaurante Panorama (jantar)", "Restaurantes", 17500, datetime.date(2026, 10, 12))
    insert_expense(conn, user_id, "Farmácia — vitaminas", "Saúde", 4200, datetime.date(2026, 10, 15))
    insert_expense(conn, user_id, "Supermercado Kero", "Alimentação", 22300, datetime.date(2026, 10, 18))
    insert_expense(conn, user_id, "Telemóvel novo (Samsung A35)", "Eletrónica", 65000, datetime.date(2026, 10, 20))
    insert_expense(conn, user_id, "Electricidade ENDE", "Habitação", 4700, datetime.date(2026, 10, 23))
    insert_expense(conn, user_id, "Combustível", "Transporte", 11800, datetime.date(2026, 10, 25))
    insert_expense(conn, user_id, "Passeio Zoo de Lagos com filha", "Lazer", 8000, datetime.date(2026, 10, 27))
    insert_transfer_out(conn, aoa_id, "Conceição Ferreira (Mãe)", 20000, datetime.date(2026, 10, 29), "Ajuda familiar mensal")

    # NOVEMBRO 2026 (1–2 Nov)
    insert_expense(conn, user_id, "Renda do apartamento", "Habitação", 65000, datetime.date(2026, 11, 1))
    insert_expense(conn, user_id, "Supermercado Nosso Super", "Alimentação", 14300, datetime.date(2026, 11, 2))

    # ── Meta de Poupança: Viagem Lisboa ───────────────────────────────────────
    insert_savings_goal(
        conn, user_id, aoa_id,
        name="Viagem a Lisboa 2027",
        target_kz=450000,
        monthly_kz=45000,
        start_date=datetime.date(2026, 8, 10),
        icon="airplane",
        deadline="2027-06-30"
    )

    # ── Depósito a Prazo ──────────────────────────────────────────────────────
    insert_investment(
        conn, user_id, aoa_id,
        name="Depósito a Prazo Super Rendimento",
        category="deposito_prazo",
        amount_kz=100000,
        rate=18.5,
        start_date=datetime.date(2026, 8, 15),
        term_months=12
    )

    print(f"   ✅ Ana criada! user_id={user_id}")
    print(f"      Email: ana.ferreira@bankao.ao | Password: Demo1234!")
    return user_id


# =============================================================================
# UTILIZADOR 2 — João Pedro Makiesse | Engenheiro | Luanda
# =============================================================================

def seed_joao(conn):
    print("\n[2/2] A criar Joao Pedro Makiesse...")

    user_id = create_user(
        conn,
        email="joao.makiesse@bankao.ao",
        nome="João Pedro Makiesse",
        primeiro_nome="João Pedro",
        ultimo_nome="Makiesse",
        telefone="+244912333444"
    )
    accs = create_accounts(conn, user_id)
    aoa_id = accs["AOA"]
    usd_id = accs["USD"]

    # ── Memória do Copilot ────────────────────────────────────────────────────
    insert_memory(conn, user_id, "nome_preferido", "João")
    insert_memory(conn, user_id, "rendimento_mensal", "400.000 Kz")
    insert_memory(conn, user_id, "rendimento_mensal_numerico", "400000")
    insert_memory(conn, user_id, "perfil_risco", "Moderado (equilíbrio entre taxa fixa e crescimento)")
    insert_memory(conn, user_id, "interesse_carro", "Meta/Gosto: Compra de Toyota Hilux")
    insert_memory(conn, user_id, "interesse_reserva", "Meta/Gosto: Fundo de reserva de emergência")
    insert_memory(conn, user_id, "habito_poupanca", "Investe regularmente em Depósitos a Prazo")

    # ── Contactos ─────────────────────────────────────────────────────────────
    insert_contact(conn, user_id, "Paulo Makiesse (Irmão)", gerar_iban_ficticio("AO"), "Irmão")
    insert_contact(conn, user_id, "Condomínio Talatona", gerar_iban_ficticio("AO"), "Condomínio")
    insert_contact(conn, user_id, "Renda Escritório", gerar_iban_ficticio("AO"), "")
    insert_contact(conn, user_id, "Carlos Silva", gerar_iban_ficticio("AO"), "Carlos")

    # ── Salários ──────────────────────────────────────────────────────────────
    for d in [
        datetime.date(2026, 8, 3),
        datetime.date(2026, 9, 3),
        datetime.date(2026, 10, 3),
    ]:
        insert_deposit_ledger(conn, user_id, aoa_id, 400000, d, "Salário — Engenharia Angola Lda.")

    # Saldo inicial + bónus de agosto
    insert_deposit_ledger(conn, user_id, aoa_id, 220000, datetime.date(2026, 8, 1), "Saldo anterior")
    insert_deposit_ledger(conn, user_id, aoa_id, 80000, datetime.date(2026, 8, 15), "Bónus de projeto")

    # Depósito USD (recebimento de consultoria)
    tx_id = make_id()
    conn.execute(
        "INSERT INTO transactions (id, type, status, description, created_at) VALUES (?,?,?,?,?)",
        (tx_id, "deposit", "completed", "Consultoria internacional — USD", "2026-09-10T14:00:00")
    )
    conn.execute(
        "INSERT INTO deposits (id, transaction_id, account_id, method, amount_minor, currency, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (make_id(), tx_id, usd_id, "multicaixa_express", kz(500), "USD", "completed", "2026-09-10T14:00:00")
    )
    conn.execute(
        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at) VALUES (?,?,?,?,?)",
        (tx_id, usd_id, kz(500), "USD", "2026-09-10T14:00:00")
    )

    # ── Despesas ──────────────────────────────────────────────────────────────

    # AGOSTO 2026
    insert_expense(conn, user_id, "Condomínio Talatona", "Habitação", 85000, datetime.date(2026, 8, 2))
    insert_expense(conn, user_id, "Combustível — Toyota Prado", "Transporte", 38000, datetime.date(2026, 8, 4))
    insert_expense(conn, user_id, "Supermercado Jumbo", "Alimentação", 42000, datetime.date(2026, 8, 6))
    insert_expense(conn, user_id, "Restaurante Navegadores (jantar clientes)", "Restaurantes", 31500, datetime.date(2026, 8, 9))
    insert_expense(conn, user_id, "Unitel Business — 3 linhas", "Telecomunicações", 18000, datetime.date(2026, 8, 11))
    insert_expense(conn, user_id, "Academia Fitness Talatona", "Saúde", 12000, datetime.date(2026, 8, 13))
    insert_expense(conn, user_id, "Electricidade ENDE", "Habitação", 9800, datetime.date(2026, 8, 16))
    insert_expense(conn, user_id, "Combustível — semana 2", "Transporte", 35000, datetime.date(2026, 8, 19))
    insert_expense(conn, user_id, "Restaurante ilha — convívio equipa", "Restaurantes", 48000, datetime.date(2026, 8, 21))
    insert_expense(conn, user_id, "Supermercado Kero", "Alimentação", 28000, datetime.date(2026, 8, 24))
    insert_expense(conn, user_id, "Roupa formal — Tailoring Luanda", "Vestuário", 35000, datetime.date(2026, 8, 26))
    insert_expense(conn, user_id, "Cinema Belas + jantares", "Lazer", 14000, datetime.date(2026, 8, 28))
    insert_transfer_out(conn, aoa_id, "Paulo Makiesse (Irmão)", 30000, datetime.date(2026, 8, 29), "Apoio propinas universidade")

    # SETEMBRO 2026
    insert_expense(conn, user_id, "Condomínio Talatona", "Habitação", 85000, datetime.date(2026, 9, 2))
    insert_expense(conn, user_id, "Combustível — Toyota Prado", "Transporte", 41000, datetime.date(2026, 9, 5))
    insert_expense(conn, user_id, "Supermercado Jumbo", "Alimentação", 38500, datetime.date(2026, 9, 7))
    insert_expense(conn, user_id, "Consulta médica particular", "Saúde", 22000, datetime.date(2026, 9, 10))
    insert_expense(conn, user_id, "Restaurante Marítimo", "Restaurantes", 26000, datetime.date(2026, 9, 13))
    insert_expense(conn, user_id, "Unitel Business", "Telecomunicações", 18000, datetime.date(2026, 9, 15))
    insert_expense(conn, user_id, "Academia Fitness", "Saúde", 12000, datetime.date(2026, 9, 17))
    insert_expense(conn, user_id, "Combustível — semana 3", "Transporte", 38000, datetime.date(2026, 9, 20))
    insert_expense(conn, user_id, "Electricidade + Água EPAL", "Habitação", 12300, datetime.date(2026, 9, 22))
    insert_expense(conn, user_id, "Jantar aniversário esposa (Ilha)", "Restaurantes", 62000, datetime.date(2026, 9, 25))
    insert_expense(conn, user_id, "Supermercado Nosso Super", "Alimentação", 31000, datetime.date(2026, 9, 27))
    insert_expense(conn, user_id, "Gadgets — teclado mecânico", "Eletrónica", 28000, datetime.date(2026, 9, 29))
    insert_transfer_out(conn, aoa_id, "Paulo Makiesse (Irmão)", 30000, datetime.date(2026, 9, 30), "Apoio propinas universidade")

    # OUTUBRO 2026
    insert_expense(conn, user_id, "Condomínio Talatona", "Habitação", 85000, datetime.date(2026, 10, 2))
    insert_expense(conn, user_id, "Combustível — Toyota Prado", "Transporte", 44000, datetime.date(2026, 10, 4))
    insert_expense(conn, user_id, "Supermercado Jumbo", "Alimentação", 45000, datetime.date(2026, 10, 6))
    insert_expense(conn, user_id, "Restaurante Caxinde — almoço trabalho", "Restaurantes", 19000, datetime.date(2026, 10, 9))
    insert_expense(conn, user_id, "Unitel Business", "Telecomunicações", 18000, datetime.date(2026, 10, 11))
    insert_expense(conn, user_id, "Academia Fitness", "Saúde", 12000, datetime.date(2026, 10, 13))
    insert_expense(conn, user_id, "Combustível — semana 3", "Transporte", 40000, datetime.date(2026, 10, 17))
    insert_expense(conn, user_id, "Electricidade ENDE", "Habitação", 10200, datetime.date(2026, 10, 20))
    insert_expense(conn, user_id, "Restaurante Atlântico — jantar família", "Restaurantes", 55000, datetime.date(2026, 10, 23))
    insert_expense(conn, user_id, "Supermercado Kero", "Alimentação", 33000, datetime.date(2026, 10, 25))
    insert_expense(conn, user_id, "Monitor 4K para escritório", "Eletrónica", 85000, datetime.date(2026, 10, 27))
    insert_expense(conn, user_id, "Passeio família — Mussulo", "Lazer", 22000, datetime.date(2026, 10, 29))
    insert_transfer_out(conn, aoa_id, "Paulo Makiesse (Irmão)", 30000, datetime.date(2026, 10, 30), "Apoio propinas universidade")

    # NOVEMBRO 2026 (1–2 Nov)
    insert_expense(conn, user_id, "Condomínio Talatona", "Habitação", 85000, datetime.date(2026, 11, 1))
    insert_expense(conn, user_id, "Combustível início novembro", "Transporte", 22000, datetime.date(2026, 11, 2))
    insert_expense(conn, user_id, "Supermercado Jumbo", "Alimentação", 19000, datetime.date(2026, 11, 2))

    # ── Meta: Compra Toyota Hilux ──────────────────────────────────────────────
    insert_savings_goal(
        conn, user_id, aoa_id,
        name="Toyota Hilux 2027",
        target_kz=3500000,
        monthly_kz=150000,
        start_date=datetime.date(2026, 8, 5),
        icon="car",
        deadline="2027-12-31"
    )

    # ── Meta: Fundo de Emergência ─────────────────────────────────────────────
    insert_savings_goal(
        conn, user_id, aoa_id,
        name="Fundo de Emergência (6 meses)",
        target_kz=2400000,
        monthly_kz=100000,
        start_date=datetime.date(2026, 8, 10),
        icon="shield",
        deadline="2028-08-10"
    )

    # ── Depósito a Prazo (AOA) ────────────────────────────────────────────────
    insert_investment(
        conn, user_id, aoa_id,
        name="Depósito a Prazo Super Rendimento",
        category="deposito_prazo",
        amount_kz=250000,
        rate=18.5,
        start_date=datetime.date(2026, 8, 20),
        term_months=12
    )

    # ── Obrigações do Tesouro BODIVA ──────────────────────────────────────────
    insert_investment(
        conn, user_id, aoa_id,
        name="OT 2027 — Obrigações do Tesouro BODIVA",
        category="obrigacoes",
        amount_kz=500000,
        rate=17.2,
        start_date=datetime.date(2026, 9, 1),
        term_months=18
    )

    print(f"   ✅ João criado! user_id={user_id}")
    print(f"      Email: joao.makiesse@bankao.ao | Password: Demo1234!")
    return user_id


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    conn = get_connection()
    try:
        with conn:
            uid_ana = seed_ana(conn)
            uid_joao = seed_joao(conn)

        print("\n" + "=" * 65)
        print("SEED CONCLUIDO COM SUCESSO!")
        print("=" * 65)
        print("\nUtilizadores criados (password: Demo1234!):")
        print("  Ana Luisa Ferreira  -> ana.ferreira@bankao.ao")
        print("  Joao Pedro Makiesse -> joao.makiesse@bankao.ao")
        print("\nHistorico gerado: Agosto 2026 -> Novembro 2026")
        print("  - Salarios mensais creditos")
        print("  - Despesas reais por categoria (Alimentacao, Transporte, Habitacao...)")
        print("  - Transferencias para contactos")
        print("  - Metas de poupanca com debitos automaticos")
        print("  - Investimentos (Deposito a Prazo, Obrigacoes do Tesouro)")
        print("  - Memoria do Copilot pre-configurada")
        print("=" * 65)

    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()
