"""
Seed de 4 utilizadores de demonstração com ~1 ano de histórico bancário realista.

Utilizadores criados:
  1. ana@bankao.ao       / Demo1234!   — Gestora de Marketing, poupanças e investimentos activos
  2. carlos@bankao.ao    / Demo1234!   — Engenheiro, transferências internacionais frequentes
  3. fatima@bankao.ao    / Demo1234!   — Professora, gestão cuidadosa de orçamentos
  4. miguel@bankao.ao    / Demo1234!   — Comerciante, volume alto de movimentos

Execute a partir da raiz do projecto:
    python scripts/seed_demo_users.py
"""

import random
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Garantir que o módulo backend é encontrado
sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt

from backend.database.connection import get_connection
from backend.services.iban import gerar_iban_ficticio

# ─── Utilitários ───────────────────────────────────────────────────────────────

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

def new_id() -> str:
    return str(uuid.uuid4())

def aoa(kwanzas: float) -> int:
    """Converte Kwanzas para cêntimos (minor units, 2 casas decimais)."""
    return int(round(kwanzas * 100))

def eur(euros: float) -> int:
    return int(round(euros * 100))

def usd(dollars: float) -> int:
    return int(round(dollars * 100))

def rnd_date(start: date, end: date) -> str:
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).isoformat()

def account_num() -> str:
    return f"0040{random.randint(10000000, 99999999)}"


# ─── Perfis dos utilizadores ───────────────────────────────────────────────────

USERS = [
    {
        "id": new_id(),
        "nome": "Ana Luísa Ferreira",
        "nome_apresentacao": "Ana Luísa",
        "primeiro_nome": "Ana Luísa",
        "ultimo_nome": "Ferreira",
        "email": "ana@bankao.ao",
        "telefone": "+244 923 456 789",
        "nacionalidade": "Angolana",
        "profissao": "Gestora de Marketing",
        "rendimento_mensal": "350000",
        "kyc_status": "verificado",
        "password": "Demo1234!",
    },
    {
        "id": new_id(),
        "nome": "Carlos Manuel Domingos",
        "nome_apresentacao": "Carlos",
        "primeiro_nome": "Carlos Manuel",
        "ultimo_nome": "Domingos",
        "email": "carlos@bankao.ao",
        "telefone": "+244 912 111 222",
        "nacionalidade": "Angolana",
        "profissao": "Engenheiro Civil",
        "rendimento_mensal": "500000",
        "kyc_status": "verificado",
        "password": "Demo1234!",
    },
    {
        "id": new_id(),
        "nome": "Fátima Beatriz Neto",
        "nome_apresentacao": "Fátima",
        "primeiro_nome": "Fátima Beatriz",
        "ultimo_nome": "Neto",
        "email": "fatima@bankao.ao",
        "telefone": "+244 935 777 888",
        "nacionalidade": "Angolana",
        "profissao": "Professora",
        "rendimento_mensal": "180000",
        "kyc_status": "verificado",
        "password": "Demo1234!",
    },
    {
        "id": new_id(),
        "nome": "Miguel António Silva",
        "nome_apresentacao": "Miguel",
        "primeiro_nome": "Miguel António",
        "ultimo_nome": "Silva",
        "email": "miguel@bankao.ao",
        "telefone": "+244 944 333 444",
        "nacionalidade": "Angolana",
        "profissao": "Comerciante",
        "rendimento_mensal": "620000",
        "kyc_status": "verificado",
        "password": "Demo1234!",
    },
]

TODAY    = date.today()
ONE_YEAR = TODAY - timedelta(days=365)


# ─── Helpers de inserção ───────────────────────────────────────────────────────

def insert_user(conn, u: dict) -> dict:
    uid = u["id"]
    pw_hash = hash_pw(u["password"])
    conn.execute("""
        INSERT OR IGNORE INTO users (
            id, nome, nome_apresentacao, primeiro_nome, ultimo_nome,
            email, telefone, nacionalidade, profissao, rendimento_mensal,
            kyc_status, password_hash, terms_accepted, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        uid, u["nome"], u["nome_apresentacao"],
        u["primeiro_nome"], u["ultimo_nome"],
        u["email"], u["telefone"],
        u["nacionalidade"], u["profissao"], u["rendimento_mensal"],
        u["kyc_status"], pw_hash,
        ONE_YEAR.isoformat()
    ))
    return u


def create_accounts(conn, uid: str) -> dict:
    """Cria 3 contas (AOA, EUR, USD) e devolve {currency: account_id}."""
    accs = {}
    for currency in ("AOA", "EUR", "USD"):
        pais = {"AOA": "AO", "EUR": "PT", "USD": "US"}[currency]
        aid = new_id()
        anum = account_num()
        iban = gerar_iban_ficticio(pais)
        conn.execute("""
            INSERT OR IGNORE INTO accounts (id, user_id, account_number, iban_virtual, currency, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (aid, uid, anum, iban, currency, ONE_YEAR.isoformat()))
        accs[currency] = {"id": aid, "iban": iban, "account_number": anum}
    return accs


def ledger_credit(conn, tx_id: str, account_id: str, amount: int, currency: str, dt: str):
    conn.execute("""
        INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (tx_id, account_id, amount, currency, dt + " 12:00:00"))


def ledger_debit(conn, tx_id: str, account_id: str, amount: int, currency: str, dt: str):
    conn.execute("""
        INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (tx_id, account_id, -amount, currency, dt + " 12:00:00"))


def make_deposit(conn, account_id: str, amount: int, currency: str, dt: str, description: str):
    tx_id = new_id()
    dep_id = new_id()
    conn.execute("""
        INSERT INTO transactions (id, type, status, description, created_at)
        VALUES (?, 'deposit', 'completed', ?, ?)
    """, (tx_id, description, dt + " 08:00:00"))
    conn.execute("""
        INSERT INTO deposits (id, transaction_id, account_id, method, amount_minor, currency, status, created_at)
        VALUES (?, ?, ?, 'multicaixa_express', ?, ?, 'completed', ?)
    """, (dep_id, tx_id, account_id, amount, currency, dt + " 08:00:00"))
    ledger_credit(conn, tx_id, account_id, amount, currency, dt)
    return tx_id


def make_internal_transfer(conn, from_id: str, to_id: str, amount: int, currency: str, dt: str, name: str):
    tx_id = new_id()
    t_id = new_id()
    fee = int(amount * 0.01)
    conn.execute("""
        INSERT INTO transactions (id, type, status, description, created_at)
        VALUES (?, 'transfer_internal', 'completed', ?, ?)
    """, (tx_id, f"Transferência para {name}", dt + " 10:00:00"))
    conn.execute("""
        INSERT INTO transfers (id, transaction_id, from_account_id, to_account_id, beneficiary_name,
            source_amount_minor, source_currency, dest_amount_minor, dest_currency,
            fx_rate, fee_minor, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, 'completed', ?)
    """, (t_id, tx_id, from_id, to_id, name, amount, currency, amount - fee, currency, fee, dt + " 10:00:00"))
    ledger_debit(conn, tx_id, from_id, amount, currency, dt)
    ledger_credit(conn, tx_id, to_id, amount - fee, currency, dt)
    return tx_id


def make_expense(conn, uid: str, name: str, category: str, amount: int, currency: str, dt: str):
    conn.execute("""
        INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?)
    """, (new_id(), uid, name, category, amount, currency, dt, dt + " 09:00:00"))


def make_savings_goal(conn, uid: str, name: str, target: int, saved: int, currency: str, icon: str, deadline: str) -> str:
    gid = new_id()
    monthly = int(target / 12)
    conn.execute("""
        INSERT INTO savings_goals (id, user_id, name, target_minor, saved_minor, monthly_minor,
            deadline, icon_key, status, currency, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'on-track', ?, ?)
    """, (gid, uid, name, target, saved, monthly, deadline, icon, currency, ONE_YEAR.isoformat()))
    return gid


def make_budget(conn, uid: str, category: str, amount: int, currency: str = "AOA"):
    conn.execute("""
        INSERT OR REPLACE INTO category_budgets (user_id, category, amount_minor, currency)
        VALUES (?, ?, ?, ?)
    """, (uid, category, amount, currency))


def make_card(conn, uid: str, account_id: str, holder: str, last_four: str, color: str = "blue"):
    cid = new_id()
    conn.execute("""
        INSERT OR IGNORE INTO cards (
            id, user_id, account_id, card_type, network, last_four,
            cardholder_name, expires_month, expires_year, status,
            is_virtual, color_scheme, institution, created_at
        ) VALUES (?, ?, ?, 'debit', 'multicaixa', ?, ?, 12, 2028, 'active', 0, ?, 'BankAO', ?)
    """, (cid, uid, account_id, last_four, holder.upper(), color, ONE_YEAR.isoformat()))
    return cid


def make_card_movement(conn, card_id: str, uid: str, amount: int, currency: str,
                        merchant: str, category: str, op_type: str, dt: str, is_debit: int = 1):
    conn.execute("""
        INSERT INTO card_movements (id, card_id, user_id, amount_minor, currency,
            merchant_name, merchant_category, operation_type, status, is_debit, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)
    """, (new_id(), card_id, uid, amount, currency, merchant, category, op_type, is_debit, dt + " 14:00:00"))


def make_investment(conn, uid: str, account_id: str, product_id: str, name: str,
                     category: str, institution: str, amount: int, rate: float,
                     start: str, maturity: str, currency: str = "AOA"):
    inv_id = new_id()
    # Calcular valorização simples
    months_elapsed = max(1, (TODAY - date.fromisoformat(start)).days // 30)
    yield_val = int(amount * (rate / 100) * (months_elapsed / 12))
    current = amount + yield_val
    conn.execute("""
        INSERT OR IGNORE INTO user_investments (
            id, user_id, product_id, name, category, institution, is_external,
            account_id, amount_invested_minor, current_value_minor, accumulated_yield_minor,
            currency, rate_annual, start_date, maturity_date, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'ativo', ?)
    """, (inv_id, uid, product_id, name, category, institution, account_id,
          amount, current, yield_val, currency, rate, start, maturity, start + " 09:00:00"))
    # Operação inicial
    conn.execute("""
        INSERT INTO investment_operations (id, investment_id, user_id, operation_type,
            amount_minor, currency, operation_date, description, created_at)
        VALUES (?, ?, ?, 'aplicacao', ?, ?, ?, 'Aplicação inicial', ?)
    """, (new_id(), inv_id, uid, amount, currency, start, start + " 09:00:00"))


# ─── Seed principal ────────────────────────────────────────────────────────────

def seed():
    conn = get_connection()

    # Verificar se utilizadores já existem
    emails = [u["email"] for u in USERS]
    existing = conn.execute(
        f"SELECT email FROM users WHERE email IN ({','.join('?'*len(emails))})", emails
    ).fetchall()
    existing_emails = {r["email"] for r in existing}
    if existing_emails:
        print(f"⚠️  Utilizadores já existem (ignorados): {', '.join(existing_emails)}")

    with conn:
        for profile in USERS:
            if profile["email"] in existing_emails:
                continue

            uid = profile["id"]
            print(f"\n[+] A criar {profile['nome']} ({profile['email']})...")

            insert_user(conn, profile)
            accs = create_accounts(conn, uid)
            aoa_id = accs["AOA"]["id"]
            eur_id = accs["EUR"]["id"]
            usd_id = accs["USD"]["id"]

            # ── Cartão de débito ───────────────────────────────────────────
            last4 = str(random.randint(1000, 9999))
            card_id = make_card(conn, uid, aoa_id, profile["nome_apresentacao"],
                                last4, ["blue", "dark", "gold", "blue"][USERS.index(profile)])

            # ══════════════════════════════════════════════════════════════
            # ANA — Gestora de Marketing, poupanças e investimentos activos
            # ══════════════════════════════════════════════════════════════
            if profile["email"] == "ana@bankao.ao":
                # Salário mensal
                for m in range(13):
                    dt = (ONE_YEAR + timedelta(days=m * 30)).isoformat()
                    make_deposit(conn, aoa_id, aoa(350_000), "AOA", dt, "Salário mensal — Empresa LuandaMedia")

                # Despesas mensais (12 meses)
                for m in range(12):
                    base = ONE_YEAR + timedelta(days=m * 30)
                    make_expense(conn, uid, "Renda do apartamento", "Habitação",   aoa(85_000), "AOA", (base + timedelta(days=1)).isoformat())
                    make_expense(conn, uid, "Supermercado Shoprite", "Alimentação", aoa(45_000 + random.randint(-5000,5000)), "AOA", (base + timedelta(days=5)).isoformat())
                    make_expense(conn, uid, "Zap Viva (TV + Net)", "Telecomunicações", aoa(18_000), "AOA", (base + timedelta(days=3)).isoformat())
                    make_expense(conn, uid, "Ginásio VIP Luanda", "Saúde",         aoa(12_000), "AOA", (base + timedelta(days=8)).isoformat())
                    make_expense(conn, uid, "Restaurante panorâmico", "Lazer",     aoa(28_000 + random.randint(-8000,8000)), "AOA", (base + timedelta(days=15)).isoformat())
                    make_expense(conn, uid, "Uber / Bolt", "Transporte",           aoa(8_000  + random.randint(-2000,2000)), "AOA", (base + timedelta(days=10)).isoformat())
                    # Movimentos no cartão
                    make_card_movement(conn, card_id, uid, aoa(45_000 + random.randint(-5000,5000)), "AOA", "Shoprite Luanda", "alimentacao", "compra", (base + timedelta(days=5)).isoformat())
                    make_card_movement(conn, card_id, uid, aoa(28_000), "AOA", "Sky Bar Talatona", "lazer", "compra", (base + timedelta(days=15)).isoformat())

                # Poupanças
                make_savings_goal(conn, uid, "Viagem a Lisboa", aoa(500_000), aoa(312_000), "AOA", "airplane", (TODAY + timedelta(days=90)).isoformat())
                make_savings_goal(conn, uid, "Fundo de Emergência", aoa(1_050_000), aoa(780_000), "AOA", "shield", (TODAY + timedelta(days=180)).isoformat())
                make_savings_goal(conn, uid, "MacBook Pro", aoa(285_000), aoa(285_000), "AOA", "laptop", TODAY.isoformat())

                # Orçamentos
                for cat, val in [("Alimentação", aoa(50_000)), ("Habitação", aoa(90_000)),
                                  ("Lazer", aoa(35_000)), ("Saúde", aoa(15_000)),
                                  ("Transporte", aoa(10_000)), ("Telecomunicações", aoa(20_000))]:
                    make_budget(conn, uid, cat, val)

                # EUR: depósito e transferência
                make_deposit(conn, eur_id, eur(1_200), "EUR", (TODAY - timedelta(days=200)).isoformat(), "Transferência da família em Portugal")
                make_deposit(conn, eur_id, eur(800), "EUR",  (TODAY - timedelta(days=60)).isoformat(),  "Pagamento freelance — projecto digital")

                # Investimentos
                make_investment(conn, uid, aoa_id, "DP-BANKAO-MAX",
                                "Depósito a Prazo Super Rendimento BankAO", "deposito_prazo", "BankAO",
                                aoa(300_000), 18.5,
                                (ONE_YEAR + timedelta(days=30)).isoformat(),
                                (TODAY + timedelta(days=335)).isoformat())
                make_investment(conn, uid, usd_id, "ETF-VWCE-GLOBAL",
                                "Vanguard FTSE All-World UCITS ETF", "etf", "Vanguard / Interactive Brokers",
                                usd(500), 10.2,
                                (ONE_YEAR + timedelta(days=90)).isoformat(),
                                None, "USD")

                print(f"   ✅ Ana: 13 depósitos · 72 despesas · 3 metas · 2 investimentos")

            # ══════════════════════════════════════════════════════════════
            # CARLOS — Engenheiro, transferências internacionais frequentes
            # ══════════════════════════════════════════════════════════════
            elif profile["email"] == "carlos@bankao.ao":
                # Salário alto
                for m in range(13):
                    dt = (ONE_YEAR + timedelta(days=m * 30)).isoformat()
                    make_deposit(conn, aoa_id, aoa(500_000), "AOA", dt, "Salário — EngWorks Angola Lda")

                # Despesas
                for m in range(12):
                    base = ONE_YEAR + timedelta(days=m * 30)
                    make_expense(conn, uid, "Renda Talatona Premium", "Habitação",    aoa(120_000), "AOA", (base + timedelta(days=1)).isoformat())
                    make_expense(conn, uid, "Continente / Jumbo",    "Alimentação",   aoa(60_000 + random.randint(-10000,10000)), "AOA", (base + timedelta(days=4)).isoformat())
                    make_expense(conn, uid, "Claro Angola 100GB",    "Telecomunicações", aoa(22_000), "AOA", (base + timedelta(days=2)).isoformat())
                    make_expense(conn, uid, "Combustível (carro)",   "Transporte",    aoa(35_000 + random.randint(-5000,5000)), "AOA", (base + timedelta(days=10)).isoformat())
                    make_expense(conn, uid, "Cinema / eventos",      "Lazer",         aoa(18_000 + random.randint(-3000,5000)), "AOA", (base + timedelta(days=20)).isoformat())
                    # Cartão
                    make_card_movement(conn, card_id, uid, aoa(60_000), "AOA", "Jumbo Luanda", "alimentacao", "compra", (base + timedelta(days=4)).isoformat())
                    make_card_movement(conn, card_id, uid, aoa(35_000), "AOA", "Shell Angola", "transporte", "compra", (base + timedelta(days=10)).isoformat())
                    if m % 3 == 0:  # Levantamento trimestral
                        make_card_movement(conn, card_id, uid, aoa(50_000), "AOA", "ATM Multicaixa", "outros", "levantamento", (base + timedelta(days=25)).isoformat())

                # EUR frequente — família em Portugal
                for m in range(12):
                    dt = (ONE_YEAR + timedelta(days=m * 30 + 15)).isoformat()
                    make_deposit(conn, eur_id, eur(300 + random.randint(-50, 100)), "EUR", dt, "Remessa familiar — Portugal")

                # Poupanças
                make_savings_goal(conn, uid, "Casa própria Luanda", aoa(15_000_000), aoa(4_200_000), "AOA", "home", (TODAY + timedelta(days=730)).isoformat())
                make_savings_goal(conn, uid, "Carro novo",           aoa(3_500_000),  aoa(2_100_000), "AOA", "car",  (TODAY + timedelta(days=180)).isoformat())

                # Orçamentos
                for cat, val in [("Alimentação", aoa(65_000)), ("Habitação", aoa(130_000)),
                                  ("Transporte", aoa(40_000)), ("Lazer", aoa(25_000)),
                                  ("Telecomunicações", aoa(25_000))]:
                    make_budget(conn, uid, cat, val)

                # Investimentos
                make_investment(conn, uid, aoa_id, "BODIVA-OT-2027",
                                "Obrigações do Tesouro OT-NR 2027", "obrigacoes", "BODIVA / MinFin",
                                aoa(500_000), 17.2,
                                (ONE_YEAR + timedelta(days=10)).isoformat(),
                                (TODAY + timedelta(days=400)).isoformat())
                make_investment(conn, uid, usd_id, "ETF-CSPX-SP500",
                                "iShares Core S&P 500 UCITS ETF", "etf", "BlackRock / Saxo Bank",
                                usd(1_000), 12.8,
                                (ONE_YEAR + timedelta(days=45)).isoformat(),
                                None, "USD")

                print(f"   ✅ Carlos: 13 depósitos · 72 despesas · 12 remessas EUR · 2 investimentos")

            # ══════════════════════════════════════════════════════════════
            # FÁTIMA — Professora, gestão cuidadosa de orçamentos
            # ══════════════════════════════════════════════════════════════
            elif profile["email"] == "fatima@bankao.ao":
                # Salário modesto
                for m in range(13):
                    dt = (ONE_YEAR + timedelta(days=m * 30)).isoformat()
                    make_deposit(conn, aoa_id, aoa(180_000), "AOA", dt, "Salário — Escola Secundária Nº12 Luanda")

                # Despesas controladas
                for m in range(12):
                    base = ONE_YEAR + timedelta(days=m * 30)
                    make_expense(conn, uid, "Renda partilhada",        "Habitação",       aoa(45_000), "AOA", (base + timedelta(days=1)).isoformat())
                    make_expense(conn, uid, "Mercado local / Feira",   "Alimentação",     aoa(32_000 + random.randint(-3000,5000)), "AOA", (base + timedelta(days=5)).isoformat())
                    make_expense(conn, uid, "Autocarro / candongueiro","Transporte",      aoa(6_000  + random.randint(-1000,1000)), "AOA", (base + timedelta(days=8)).isoformat())
                    make_expense(conn, uid, "Unitel 20GB",             "Telecomunicações",aoa(8_500), "AOA", (base + timedelta(days=2)).isoformat())
                    make_expense(conn, uid, "Farmácia / consulta",     "Saúde",           aoa(12_000 + random.randint(0,8000)), "AOA", (base + timedelta(days=12)).isoformat())
                    if m % 2 == 0:
                        make_expense(conn, uid, "Cinema ou teatro",    "Lazer",           aoa(6_000), "AOA", (base + timedelta(days=22)).isoformat())
                    # Cartão
                    make_card_movement(conn, card_id, uid, aoa(32_000), "AOA", "Mercado Roque Santeiro", "alimentacao", "compra", (base + timedelta(days=5)).isoformat())

                # Poupanças — disciplinada
                make_savings_goal(conn, uid, "Pós-graduação em Lisboa", aoa(800_000), aoa(290_000), "AOA", "book", (TODAY + timedelta(days=365)).isoformat())
                make_savings_goal(conn, uid, "Fundo de emergência",     aoa(360_000), aoa(360_000), "AOA", "shield", TODAY.isoformat())
                make_savings_goal(conn, uid, "Telemóvel novo",          aoa(85_000),  aoa(60_000),  "AOA", "phone", (TODAY + timedelta(days=45)).isoformat())

                # Orçamentos
                for cat, val in [("Alimentação", aoa(35_000)), ("Habitação", aoa(50_000)),
                                  ("Saúde", aoa(15_000)), ("Transporte", aoa(8_000)),
                                  ("Telecomunicações", aoa(10_000)), ("Lazer", aoa(8_000))]:
                    make_budget(conn, uid, cat, val)

                # Investimento conservador
                make_investment(conn, uid, aoa_id, "FND-BAI-LIQUIDEZ",
                                "Fundo de Liquidez e Tesouraria BAI", "fundos", "BAI Gestão de Ativos",
                                aoa(50_000), 16.6,
                                (ONE_YEAR + timedelta(days=60)).isoformat(),
                                None)

                print(f"   ✅ Fátima: 13 depósitos · 90 despesas · 3 metas · 1 investimento")

            # ══════════════════════════════════════════════════════════════
            # MIGUEL — Comerciante, volume alto de movimentos
            # ══════════════════════════════════════════════════════════════
            elif profile["email"] == "miguel@bankao.ao":
                # Rendimento variável de comerciante — depósitos irregulares
                for m in range(12):
                    base = ONE_YEAR + timedelta(days=m * 30)
                    # 2 a 4 depósitos por mês (vendas)
                    for _ in range(random.randint(2, 4)):
                        amt = aoa(random.randint(80_000, 200_000))
                        dt  = rnd_date(base, base + timedelta(days=28))
                        make_deposit(conn, aoa_id, amt, "AOA", dt, "Recebimento de cliente — Loja MiguelStore")

                # Despesas de negócio e pessoais
                for m in range(12):
                    base = ONE_YEAR + timedelta(days=m * 30)
                    make_expense(conn, uid, "Armazém / loja aluguer",  "Habitação",    aoa(95_000), "AOA", (base + timedelta(days=1)).isoformat())
                    make_expense(conn, uid, "Restock de mercadoria",   "Outros",       aoa(120_000 + random.randint(-20000,30000)), "AOA", (base + timedelta(days=5)).isoformat())
                    make_expense(conn, uid, "Combustível + entrega",   "Transporte",   aoa(45_000 + random.randint(-5000,10000)), "AOA", (base + timedelta(days=10)).isoformat())
                    make_expense(conn, uid, "ENDE (electricidade)",    "Habitação",    aoa(18_000 + random.randint(0,5000)), "AOA", (base + timedelta(days=3)).isoformat())
                    make_expense(conn, uid, "Supermercado família",    "Alimentação",  aoa(55_000 + random.randint(-8000,8000)), "AOA", (base + timedelta(days=7)).isoformat())
                    make_expense(conn, uid, "Claro Angola",            "Telecomunicações", aoa(28_000), "AOA", (base + timedelta(days=2)).isoformat())
                    make_expense(conn, uid, "Restaurante / convívio",  "Lazer",        aoa(35_000 + random.randint(-10000,10000)), "AOA", (base + timedelta(days=20)).isoformat())
                    # Cartão — compras de negócio
                    make_card_movement(conn, card_id, uid, aoa(120_000 + random.randint(-20000,30000)), "AOA", "Distribuidora Angola", "outros", "compra", (base + timedelta(days=5)).isoformat())
                    make_card_movement(conn, card_id, uid, aoa(45_000), "AOA", "Shell Viana", "transporte", "compra", (base + timedelta(days=10)).isoformat())
                    make_card_movement(conn, card_id, uid, aoa(55_000), "AOA", "Shoprite Viana", "alimentacao", "compra", (base + timedelta(days=7)).isoformat())
                    # Levantamento frequente (comerciante usa dinheiro físico)
                    make_card_movement(conn, card_id, uid, aoa(100_000), "AOA", "ATM Multicaixa Viana", "outros", "levantamento", (base + timedelta(days=15)).isoformat())

                # USD — importações
                for m in range(6):
                    dt = (ONE_YEAR + timedelta(days=m * 60 + 20)).isoformat()
                    make_deposit(conn, usd_id, usd(500 + random.randint(-100, 300)), "USD", dt, "Importação mercadoria China/Dubai")

                # Poupanças
                make_savings_goal(conn, uid, "Expansão da loja",    aoa(5_000_000), aoa(1_800_000), "AOA", "store",   (TODAY + timedelta(days=365)).isoformat())
                make_savings_goal(conn, uid, "Viatura comercial",   aoa(2_800_000), aoa(950_000),   "AOA", "car",     (TODAY + timedelta(days=270)).isoformat())
                make_savings_goal(conn, uid, "Fundo de emergência", aoa(620_000),   aoa(620_000),   "AOA", "shield",  TODAY.isoformat())

                # Orçamentos
                for cat, val in [("Alimentação", aoa(60_000)), ("Transporte", aoa(50_000)),
                                  ("Lazer", aoa(40_000)), ("Telecomunicações", aoa(30_000)),
                                  ("Habitação", aoa(120_000)), ("Outros", aoa(150_000))]:
                    make_budget(conn, uid, cat, val)

                # Investimentos
                make_investment(conn, uid, aoa_id, "DP-BFA-CRESCENTE",
                                "Depósito Trimestral Crescente BFA", "deposito_prazo", "Banco BFA",
                                aoa(500_000), 15.0,
                                (ONE_YEAR + timedelta(days=20)).isoformat(),
                                (TODAY + timedelta(days=90)).isoformat())
                make_investment(conn, uid, aoa_id, "FII-ATLANTICO",
                                "Fundo de Investimento Imobiliário Atlântico", "fundos", "Banco Atlântico Gestão de Ativos",
                                aoa(200_000), 14.8,
                                (ONE_YEAR + timedelta(days=120)).isoformat(),
                                (TODAY + timedelta(days=720)).isoformat())

                print(f"   ✅ Miguel: depósitos variados · 108 despesas · 3 metas · 2 investimentos")

    conn.close()
    print("\n🎉 Seed concluído! 4 utilizadores de demonstração criados.")
    print("\n📋 Credenciais de acesso:")
    print("   Email                 | Senha      | Perfil")
    print("   ----------------------|------------|---------------------------")
    for u in USERS:
        if u["email"] not in existing_emails:
            print(f"   {u['email']:<21} | Demo1234!  | {u['profissao']}")


if __name__ == "__main__":
    seed()
