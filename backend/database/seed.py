"""
Seed de utilizadores de demonstração com ~1 ano de histórico bancário realista.
Garante que em qualquer ambiente (Render, Railway, Docker, Localhost) existam
utilizadores prontos a testar imediatamente sem necessidade de comandos manuais.

Utilizadores:
  1. ana@bankao.ao    / Demo1234!  — Gestora de Marketing, poupanças e investimentos
  2. carlos@bankao.ao / Demo1234!  — Engenheiro, transferências internacionais EUR
  3. fatima@bankao.ao / Demo1234!  — Professora, gestão orçamental rigorosa
  4. miguel@bankao.ao / Demo1234!  — Comerciante, volume comercial e USD
"""
import logging
import random
import uuid
from datetime import date, timedelta
from typing import Optional

import bcrypt

from backend.database.connection import get_connection
from backend.services.iban import gerar_iban_ficticio

logger = logging.getLogger("bankao.seed")


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def new_id() -> str:
    return str(uuid.uuid4())


def aoa(kwanzas: float) -> int:
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


TODAY = date.today()
ONE_YEAR = TODAY - timedelta(days=365)

USERS_SPEC = [
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


def insert_user(conn, u: dict) -> dict:
    uid = u["id"]
    pw_hash = hash_pw(u["password"])
    conn.execute(
        """
        INSERT OR IGNORE INTO users (
            id, nome, nome_apresentacao, primeiro_nome, ultimo_nome,
            email, telefone, nacionalidade, profissao, rendimento_mensal,
            kyc_status, password_hash, terms_accepted, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """,
        (
            uid,
            u["nome"],
            u["nome_apresentacao"],
            u["primeiro_nome"],
            u["ultimo_nome"],
            u["email"],
            u["telefone"],
            u["nacionalidade"],
            u["profissao"],
            u["rendimento_mensal"],
            u["kyc_status"],
            pw_hash,
            ONE_YEAR.isoformat(),
        ),
    )
    return u


def create_accounts(conn, uid: str) -> dict:
    accs = {}
    for currency in ("AOA", "EUR", "USD"):
        pais = {"AOA": "AO", "EUR": "PT", "USD": "US"}[currency]
        aid = new_id()
        anum = account_num()
        iban = gerar_iban_ficticio(pais)
        conn.execute(
            """
            INSERT OR IGNORE INTO accounts (id, user_id, account_number, iban_virtual, currency, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (aid, uid, anum, iban, currency, ONE_YEAR.isoformat()),
        )
        accs[currency] = {"id": aid, "iban": iban, "account_number": anum}
    return accs


def ledger_credit(conn, tx_id: str, account_id: str, amount: int, currency: str, dt: str):
    conn.execute(
        """
        INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (tx_id, account_id, amount, currency, dt + " 12:00:00"),
    )


def ledger_debit(conn, tx_id: str, account_id: str, amount: int, currency: str, dt: str):
    conn.execute(
        """
        INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (tx_id, account_id, -amount, currency, dt + " 12:00:00"),
    )


def make_deposit(conn, account_id: str, amount: int, currency: str, dt: str, description: str):
    tx_id = new_id()
    dep_id = new_id()
    conn.execute(
        """
        INSERT INTO transactions (id, type, status, description, created_at)
        VALUES (?, 'deposit', 'completed', ?, ?)
    """,
        (tx_id, description, dt + " 08:00:00"),
    )
    conn.execute(
        """
        INSERT INTO deposits (id, transaction_id, account_id, method, amount_minor, currency, status, created_at)
        VALUES (?, ?, ?, 'multicaixa_express', ?, ?, 'completed', ?)
    """,
        (dep_id, tx_id, account_id, amount, currency, dt + " 08:00:00"),
    )
    ledger_credit(conn, tx_id, account_id, amount, currency, dt)
    return tx_id


def make_expense(conn, uid: str, name: str, category: str, amount: int, currency: str, dt: str):
    conn.execute(
        """
        INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?)
    """,
        (new_id(), uid, name, category, amount, currency, dt, dt + " 09:00:00"),
    )


def make_savings_goal(
    conn, uid: str, name: str, target: int, saved: int, currency: str, icon: str, deadline: str
) -> str:
    gid = new_id()
    monthly = int(target / 12)
    conn.execute(
        """
        INSERT INTO savings_goals (id, user_id, name, target_minor, saved_minor, monthly_minor,
            deadline, icon_key, status, currency, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'on-track', ?, ?)
    """,
        (gid, uid, name, target, saved, monthly, deadline, icon, currency, ONE_YEAR.isoformat()),
    )
    return gid


def make_budget(conn, uid: str, category: str, amount: int, currency: str = "AOA"):
    conn.execute(
        """
        INSERT OR REPLACE INTO category_budgets (user_id, category, amount_minor, currency)
        VALUES (?, ?, ?, ?)
    """,
        (uid, category, amount, currency),
    )


def make_card(conn, uid: str, account_id: str, holder: str, last_four: str, color: str = "blue"):
    cid = new_id()
    conn.execute(
        """
        INSERT OR IGNORE INTO cards (
            id, user_id, account_id, card_type, network, last_four,
            cardholder_name, expires_month, expires_year, status,
            is_virtual, color_scheme, institution, created_at
        ) VALUES (?, ?, ?, 'debit', 'multicaixa', ?, ?, 12, 2028, 'active', 0, ?, 'BankAO', ?)
    """,
        (cid, uid, account_id, last_four, holder.upper(), color, ONE_YEAR.isoformat()),
    )
    return cid


def make_card_movement(
    conn,
    card_id: str,
    uid: str,
    amount: int,
    currency: str,
    merchant: str,
    category: str,
    op_type: str,
    dt: str,
    is_debit: int = 1,
):
    conn.execute(
        """
        INSERT INTO card_movements (id, card_id, user_id, amount_minor, currency,
            merchant_name, merchant_category, operation_type, status, is_debit, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)
    """,
        (new_id(), card_id, uid, amount, currency, merchant, category, op_type, is_debit, dt + " 14:00:00"),
    )


def make_investment(
    conn,
    uid: str,
    account_id: str,
    product_id: str,
    name: str,
    category: str,
    institution: str,
    amount: int,
    rate: float,
    start: str,
    maturity: Optional[str],
    currency: str = "AOA",
):
    inv_id = new_id()
    months_elapsed = max(1, (TODAY - date.fromisoformat(start)).days // 30)
    yield_val = int(amount * (rate / 100) * (months_elapsed / 12))
    current = amount + yield_val
    conn.execute(
        """
        INSERT OR IGNORE INTO user_investments (
            id, user_id, product_id, name, category, institution, is_external,
            account_id, amount_invested_minor, current_value_minor, accumulated_yield_minor,
            currency, rate_annual, start_date, maturity_date, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'ativo', ?)
    """,
        (
            inv_id,
            uid,
            product_id,
            name,
            category,
            institution,
            account_id,
            amount,
            current,
            yield_val,
            currency,
            rate,
            start,
            maturity,
            start + " 09:00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO investment_operations (id, investment_id, user_id, operation_type,
            amount_minor, currency, operation_date, description, created_at)
        VALUES (?, ?, ?, 'aplicacao', ?, ?, ?, 'Aplicação inicial', ?)
    """,
        (new_id(), inv_id, uid, amount, currency, start, start + " 09:00:00"),
    )


def seed_demo_users():
    """
    Verifica se os utilizadores de demonstração já existem. Se não existirem,
    popula o banco com contas, cartões, despesas e investimentos de 1 ano.
    Seguro para ser executado a cada arranque do servidor.
    """
    conn = get_connection()
    try:
        # Se os 4 utilizadores já existem, nada a fazer
        emails = [u["email"] for u in USERS_SPEC]
        existing = conn.execute(
            f"SELECT email FROM users WHERE email IN ({','.join('?'*len(emails))})", emails
        ).fetchall()
        existing_emails = {r["email"] for r in existing}

        if len(existing_emails) == len(emails):
            return

        with conn:
            for profile in USERS_SPEC:
                if profile["email"] in existing_emails:
                    continue

                uid = profile["id"]
                insert_user(conn, profile)
                accs = create_accounts(conn, uid)
                aoa_id = accs["AOA"]["id"]
                eur_id = accs["EUR"]["id"]
                usd_id = accs["USD"]["id"]

                idx = USERS_SPEC.index(profile)
                colors = ["blue", "dark", "gold", "blue"]
                card_id = make_card(
                    conn,
                    uid,
                    aoa_id,
                    profile["nome_apresentacao"],
                    str(random.randint(1000, 9999)),
                    colors[idx],
                )

                # ── Ana Luísa Ferreira ──────────────────────────
                if profile["email"] == "ana@bankao.ao":
                    for m in range(13):
                        dt = (ONE_YEAR + timedelta(days=m * 30)).isoformat()
                        make_deposit(conn, aoa_id, aoa(350_000), "AOA", dt, "Salário mensal — LuandaMedia Lda")

                    for m in range(12):
                        base = ONE_YEAR + timedelta(days=m * 30)
                        make_expense(conn, uid, "Renda apartamento", "Habitação", aoa(85_000), "AOA", (base + timedelta(days=1)).isoformat())
                        make_expense(conn, uid, "Supermercado Shoprite", "Alimentação", aoa(45_000 + random.randint(-5000, 5000)), "AOA", (base + timedelta(days=5)).isoformat())
                        make_expense(conn, uid, "Zap Viva Net", "Telecomunicações", aoa(18_000), "AOA", (base + timedelta(days=3)).isoformat())
                        make_expense(conn, uid, "Ginásio VIP", "Saúde", aoa(12_000), "AOA", (base + timedelta(days=8)).isoformat())
                        make_expense(conn, uid, "Restaurante", "Lazer", aoa(28_000), "AOA", (base + timedelta(days=15)).isoformat())
                        make_expense(conn, uid, "Transportes", "Transporte", aoa(8_000), "AOA", (base + timedelta(days=10)).isoformat())
                        make_card_movement(conn, card_id, uid, aoa(45_000), "AOA", "Shoprite Luanda", "alimentacao", "compra", (base + timedelta(days=5)).isoformat())

                    make_savings_goal(conn, uid, "Viagem a Lisboa", aoa(500_000), aoa(312_000), "AOA", "airplane", (TODAY + timedelta(days=90)).isoformat())
                    make_savings_goal(conn, uid, "Fundo de Emergência", aoa(1_050_000), aoa(780_000), "AOA", "shield", (TODAY + timedelta(days=180)).isoformat())
                    make_savings_goal(conn, uid, "MacBook Pro", aoa(285_000), aoa(285_000), "AOA", "laptop", TODAY.isoformat())

                    for cat, val in [("Alimentação", aoa(50_000)), ("Habitação", aoa(90_000)), ("Lazer", aoa(35_000)), ("Saúde", aoa(15_000))]:
                        make_budget(conn, uid, cat, val)

                    make_deposit(conn, eur_id, eur(1_200), "EUR", (TODAY - timedelta(days=200)).isoformat(), "Transferência familiar Lisboa")
                    make_deposit(conn, eur_id, eur(800), "EUR", (TODAY - timedelta(days=60)).isoformat(), "Freelance design digital")

                    make_investment(conn, uid, aoa_id, "DP-BANKAO-MAX", "Depósito a Prazo Super Rendimento BankAO", "deposito_prazo", "BankAO", aoa(300_000), 18.5, (ONE_YEAR + timedelta(days=30)).isoformat(), (TODAY + timedelta(days=335)).isoformat())
                    make_investment(conn, uid, usd_id, "ETF-VWCE-GLOBAL", "Vanguard FTSE All-World UCITS ETF", "etf", "Vanguard / Interactive Brokers", usd(500), 10.2, (ONE_YEAR + timedelta(days=90)).isoformat(), None, "USD")

                # ── Carlos Manuel Domingos ──────────────────────
                elif profile["email"] == "carlos@bankao.ao":
                    for m in range(13):
                        dt = (ONE_YEAR + timedelta(days=m * 30)).isoformat()
                        make_deposit(conn, aoa_id, aoa(500_000), "AOA", dt, "Salário — EngWorks Angola Lda")

                    for m in range(12):
                        base = ONE_YEAR + timedelta(days=m * 30)
                        make_expense(conn, uid, "Renda Talatona", "Habitação", aoa(120_000), "AOA", (base + timedelta(days=1)).isoformat())
                        make_expense(conn, uid, "Supermercado Jumbo", "Alimentação", aoa(60_000), "AOA", (base + timedelta(days=4)).isoformat())
                        make_expense(conn, uid, "Combustível", "Transporte", aoa(35_000), "AOA", (base + timedelta(days=10)).isoformat())
                        make_expense(conn, uid, "Lazer e eventos", "Lazer", aoa(18_000), "AOA", (base + timedelta(days=20)).isoformat())
                        make_card_movement(conn, card_id, uid, aoa(60_000), "AOA", "Jumbo Luanda", "alimentacao", "compra", (base + timedelta(days=4)).isoformat())

                    for m in range(12):
                        dt = (ONE_YEAR + timedelta(days=m * 30 + 15)).isoformat()
                        make_deposit(conn, eur_id, eur(350), "EUR", dt, "Remessa familiar — Portugal")

                    make_savings_goal(conn, uid, "Casa própria Luanda", aoa(15_000_000), aoa(4_200_000), "AOA", "home", (TODAY + timedelta(days=730)).isoformat())
                    make_savings_goal(conn, uid, "Carro novo", aoa(3_500_000), aoa(2_100_000), "AOA", "car", (TODAY + timedelta(days=180)).isoformat())

                    for cat, val in [("Alimentação", aoa(65_000)), ("Habitação", aoa(130_000)), ("Transporte", aoa(40_000))]:
                        make_budget(conn, uid, cat, val)

                    make_investment(conn, uid, aoa_id, "BODIVA-OT-2027", "Obrigações do Tesouro OT-NR 2027", "obrigacoes", "BODIVA / MinFin", aoa(500_000), 17.2, (ONE_YEAR + timedelta(days=10)).isoformat(), (TODAY + timedelta(days=400)).isoformat())
                    make_investment(conn, uid, usd_id, "ETF-CSPX-SP500", "iShares Core S&P 500 UCITS ETF", "etf", "BlackRock / Saxo Bank", usd(1_000), 12.8, (ONE_YEAR + timedelta(days=45)).isoformat(), None, "USD")

                # ── Fátima Beatriz Neto ────────────────────────
                elif profile["email"] == "fatima@bankao.ao":
                    for m in range(13):
                        dt = (ONE_YEAR + timedelta(days=m * 30)).isoformat()
                        make_deposit(conn, aoa_id, aoa(180_000), "AOA", dt, "Salário — Ministério da Educação")

                    for m in range(12):
                        base = ONE_YEAR + timedelta(days=m * 30)
                        make_expense(conn, uid, "Renda quarto", "Habitação", aoa(45_000), "AOA", (base + timedelta(days=1)).isoformat())
                        make_expense(conn, uid, "Mercado Feira", "Alimentação", aoa(32_000), "AOA", (base + timedelta(days=5)).isoformat())
                        make_expense(conn, uid, "Transporte público", "Transporte", aoa(6_000), "AOA", (base + timedelta(days=8)).isoformat())
                        make_expense(conn, uid, "Unitel 20GB", "Telecomunicações", aoa(8_500), "AOA", (base + timedelta(days=2)).isoformat())
                        make_expense(conn, uid, "Farmácia", "Saúde", aoa(12_000), "AOA", (base + timedelta(days=12)).isoformat())
                        make_card_movement(conn, card_id, uid, aoa(32_000), "AOA", "Mercado Feira Luanda", "alimentacao", "compra", (base + timedelta(days=5)).isoformat())

                    make_savings_goal(conn, uid, "Pós-graduação em Lisboa", aoa(800_000), aoa(290_000), "AOA", "book", (TODAY + timedelta(days=365)).isoformat())
                    make_savings_goal(conn, uid, "Fundo de emergência", aoa(360_000), aoa(360_000), "AOA", "shield", TODAY.isoformat())
                    make_savings_goal(conn, uid, "Telemóvel novo", aoa(85_000), aoa(60_000), "AOA", "phone", (TODAY + timedelta(days=45)).isoformat())

                    for cat, val in [("Alimentação", aoa(35_000)), ("Habitação", aoa(50_000)), ("Saúde", aoa(15_000))]:
                        make_budget(conn, uid, cat, val)

                    make_investment(conn, uid, aoa_id, "FND-BAI-LIQUIDEZ", "Fundo de Liquidez e Tesouraria BAI", "fundos", "BAI Gestão de Ativos", aoa(50_000), 16.6, (ONE_YEAR + timedelta(days=60)).isoformat(), None)

                # ── Miguel António Silva ───────────────────────
                elif profile["email"] == "miguel@bankao.ao":
                    for m in range(12):
                        base = ONE_YEAR + timedelta(days=m * 30)
                        for _ in range(3):
                            amt = aoa(random.randint(90_000, 180_000))
                            dt = rnd_date(base, base + timedelta(days=28))
                            make_deposit(conn, aoa_id, amt, "AOA", dt, "Recebimento comercial — MiguelStore")

                    for m in range(12):
                        base = ONE_YEAR + timedelta(days=m * 30)
                        make_expense(conn, uid, "Armazém loja", "Habitação", aoa(95_000), "AOA", (base + timedelta(days=1)).isoformat())
                        make_expense(conn, uid, "Mercadoria stock", "Outros", aoa(130_000), "AOA", (base + timedelta(days=5)).isoformat())
                        make_expense(conn, uid, "Combustível logística", "Transporte", aoa(45_000), "AOA", (base + timedelta(days=10)).isoformat())
                        make_expense(conn, uid, "Supermercado casa", "Alimentação", aoa(55_000), "AOA", (base + timedelta(days=7)).isoformat())
                        make_card_movement(conn, card_id, uid, aoa(130_000), "AOA", "Distribuidora Angola", "outros", "compra", (base + timedelta(days=5)).isoformat())

                    for m in range(6):
                        dt = (ONE_YEAR + timedelta(days=m * 60 + 20)).isoformat()
                        make_deposit(conn, usd_id, usd(500), "USD", dt, "Importação mercadoria China/Dubai")

                    make_savings_goal(conn, uid, "Expansão da loja", aoa(5_000_000), aoa(1_800_000), "AOA", "store", (TODAY + timedelta(days=365)).isoformat())
                    make_savings_goal(conn, uid, "Viatura comercial", aoa(2_800_000), aoa(950_000), "AOA", "car", (TODAY + timedelta(days=270)).isoformat())
                    make_savings_goal(conn, uid, "Fundo de emergência", aoa(620_000), aoa(620_000), "AOA", "shield", TODAY.isoformat())

                    for cat, val in [("Alimentação", aoa(60_000)), ("Transporte", aoa(50_000)), ("Habitação", aoa(120_000))]:
                        make_budget(conn, uid, cat, val)

                    make_investment(conn, uid, aoa_id, "DP-BFA-CRESCENTE", "Depósito Trimestral Crescente BFA", "deposito_prazo", "Banco BFA", aoa(500_000), 15.0, (ONE_YEAR + timedelta(days=20)).isoformat(), (TODAY + timedelta(days=90)).isoformat())
                    make_investment(conn, uid, aoa_id, "FII-ATLANTICO", "Fundo de Investimento Imobiliário Atlântico", "fundos", "Banco Atlântico Gestão de Ativos", aoa(200_000), 14.8, (ONE_YEAR + timedelta(days=120)).isoformat(), (TODAY + timedelta(days=720)).isoformat())

        logger.info("Seed de demonstração verificado e pronto.")
    finally:
        conn.close()
