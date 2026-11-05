"""
Criação das tabelas do livro-razão e migrações seguras. Não insere saldos nem movimentos fictícios:
só há dados reais (criados pelos utilizadores) e as taxas de câmbio de referência.
"""
import random
import sqlite3
import uuid

from backend.database.connection import get_connection
from backend.services.iban import gerar_iban_ficticio


def init_db():
    """Inicializa as tabelas do sistema bancário e livro-razão."""
    conn = get_connection()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            primeiro_nome TEXT,
            ultimo_nome TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            telefone TEXT,
            kyc_status TEXT DEFAULT 'pendente', -- 'pendente', 'verificado', 'bloqueado'
            nome_pai TEXT,
            nome_mae TEXT,
            doc_tipo TEXT,                      -- 'bilhete', 'passaporte'
            doc_numero TEXT,                    -- NIF ou N.º passaporte
            morada TEXT,
            data_emissao TEXT,
            terms_accepted INTEGER DEFAULT 1,
            nome_apresentacao TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_number TEXT UNIQUE NOT NULL,
            iban_virtual TEXT UNIQUE NOT NULL,
            currency TEXT NOT NULL, -- 'AOA', 'EUR', 'USD'
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL, -- 'deposit', 'transfer_internal', 'transfer_iban', 'fx_exchange'
            status TEXT NOT NULL, -- 'pending', 'completed', 'failed'
            idempotency_key TEXT UNIQUE,
            description TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            amount_minor INTEGER NOT NULL, -- Valores em cêntimos (+ crédito, - débito)
            currency TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS deposits (
            id TEXT PRIMARY KEY,
            transaction_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            method TEXT NOT NULL, -- 'multicaixa_express', 'referencia'
            amount_minor INTEGER NOT NULL,
            currency TEXT NOT NULL,
            reference_code TEXT, -- Para depósitos por referência
            entidade_code TEXT, -- Entidade (ex: 00123)
            phone_number TEXT,  -- Para Multicaixa Express
            status TEXT NOT NULL, -- 'pending', 'completed', 'rejected', 'expired'
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS transfers (
            id TEXT PRIMARY KEY,
            transaction_id TEXT NOT NULL,
            from_account_id TEXT NOT NULL,
            to_account_id TEXT, -- preenchido em transferência interna
            to_iban TEXT,       -- preenchido em transferência externa
            beneficiary_name TEXT NOT NULL,
            source_amount_minor INTEGER NOT NULL,
            source_currency TEXT NOT NULL,
            dest_amount_minor INTEGER NOT NULL,
            dest_currency TEXT NOT NULL,
            fx_rate REAL DEFAULT 1.0,
            fee_minor INTEGER DEFAULT 0,
            status TEXT NOT NULL, -- 'pending', 'completed', 'failed'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id),
            FOREIGN KEY (from_account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,            -- 'internal' (cliente BankAO) | 'iban'
            ref_key TEXT NOT NULL,         -- 'u:<user_id>' (interno) ou 'i:<IBAN>' (externo); evita duplicados
            name TEXT NOT NULL,
            nickname TEXT,
            account_number TEXT,           -- só internos
            iban TEXT,                     -- só externos
            favorite INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, ref_key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fx_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_currency TEXT NOT NULL,
            quote_currency TEXT NOT NULL,
            rate REAL NOT NULL,
            fee_percentage REAL DEFAULT 0.015, -- 1.5% taxa de spread/serviço
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(base_currency, quote_currency)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS savings_goals (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            target_minor INTEGER NOT NULL,
            saved_minor INTEGER NOT NULL DEFAULT 0,
            monthly_minor INTEGER NOT NULL DEFAULT 0,
            deadline TEXT,
            icon_key TEXT DEFAULT 'target',
            status TEXT DEFAULT 'on-track', -- 'on-track', 'at-risk', 'completed'
            currency TEXT NOT NULL DEFAULT 'AOA',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Outros',
            amount_minor INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'AOA',
            expense_date TEXT NOT NULL,          -- AAAA-MM-DD
            origin TEXT NOT NULL DEFAULT 'manual', -- 'manual', 'ai', 'savings'
            notes TEXT,
            goal_id TEXT,                         -- preenchido nos depósitos em metas de poupança
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (goal_id) REFERENCES savings_goals(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS category_budgets (
            user_id TEXT NOT NULL,
            category TEXT NOT NULL,
            amount_minor INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'AOA',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, category),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        -- Índices para performance
        CREATE INDEX IF NOT EXISTS idx_ledger_account ON ledger_entries(account_id);
        CREATE INDEX IF NOT EXISTS idx_ledger_tx ON ledger_entries(transaction_id);
        CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at);
        CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, expense_date);
        CREATE INDEX IF NOT EXISTS idx_goals_user ON savings_goals(user_id);
        """)

        # Migração segura para colunas adicionais de KYC se o banco já existir
        novas_colunas = [
            ("primeiro_nome", "TEXT"),
            ("ultimo_nome", "TEXT"),
            ("nome_pai", "TEXT"),
            ("nome_mae", "TEXT"),
            ("doc_tipo", "TEXT"),
            ("doc_numero", "TEXT"),
            ("morada", "TEXT"),
            ("data_emissao", "TEXT"),
            ("terms_accepted", "INTEGER DEFAULT 1"),
            ("data_nascimento", "TEXT"),
            ("nacionalidade", "TEXT"),
            ("profissao", "TEXT"),
            ("rendimento_mensal", "TEXT"),
            ("finalidade", "TEXT"),
            ("pin_hash", "TEXT"),
            ("nome_apresentacao", "TEXT")
        ]
        for col_nome, col_tipo in novas_colunas:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col_nome} {col_tipo};")
            except sqlite3.OperationalError:
                pass
        
        # Débito automático das metas de poupança (dia do mês + primeira data de débito)
        for col_nome, col_tipo in [("debit_day", "INTEGER"), ("start_date", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE savings_goals ADD COLUMN {col_nome} {col_tipo};")
            except sqlite3.OperationalError:
                pass

        # Taxas de câmbio de referência (tabela fx_rates): são a fonte única de câmbio da aplicação
        conn.execute("""
        INSERT OR IGNORE INTO fx_rates (base_currency, quote_currency, rate, fee_percentage)
        VALUES 
            ('EUR', 'AOA', 1050.00, 0.015),
            ('AOA', 'EUR', 0.000952, 0.015),
            ('USD', 'AOA', 1000.00, 0.015),
            ('AOA', 'USD', 0.001, 0.015),
            ('EUR', 'USD', 1.08, 0.010),
            ('USD', 'EUR', 0.925, 0.010);
        """)

        # Garantir carteira em USD para utilizadores existentes
        try:
            users_sem_usd = conn.execute("""
                SELECT u.id FROM users u
                WHERE NOT EXISTS (SELECT 1 FROM accounts a WHERE a.user_id = u.id AND a.currency = 'USD')
            """).fetchall()
            for u in users_sem_usd:
                uid = u["id"]
                aid = str(uuid.uuid4())
                anum = f"0060{random.randint(10000000, 99999999)}"
                iban = gerar_iban_ficticio("US")
                conn.execute(
                    "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'USD')",
                    (aid, uid, anum, iban)
                )
        except Exception:
            pass

        # Tabelas do Módulo de Investimentos
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS investment_products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL, -- 'deposito_prazo', 'obrigacoes', 'etf', 'fundos', 'acoes'
            institution TEXT NOT NULL,
            provider_api TEXT DEFAULT 'open_banking',
            currency TEXT NOT NULL DEFAULT 'AOA',
            rate_annual REAL NOT NULL, -- Ex: 18.5 para 18.5% ao ano
            term_months INTEGER,       -- null se aberto/contínuo
            min_amount_minor INTEGER NOT NULL DEFAULT 1000000, -- em cêntimos (ex: 10.000,00 kz)
            risk_level TEXT NOT NULL DEFAULT 'baixo', -- 'baixo', 'moderado', 'alto', 'muito_alto'
            liquidity TEXT NOT NULL DEFAULT 'no_vencimento',
            fees_info TEXT,
            redemption_conditions TEXT,
            description TEXT,
            current_price REAL DEFAULT 1.0,
            is_active INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_investments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_id TEXT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            institution TEXT NOT NULL,
            is_external INTEGER NOT NULL DEFAULT 0, -- 0 = BankAO, 1 = Externo
            account_id TEXT,
            amount_invested_minor INTEGER NOT NULL,
            current_value_minor INTEGER NOT NULL,
            accumulated_yield_minor INTEGER NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'AOA',
            rate_annual REAL DEFAULT 0.0,
            start_date TEXT NOT NULL,
            maturity_date TEXT,
            status TEXT NOT NULL DEFAULT 'ativo', -- 'ativo', 'resgatado', 'vencido'
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES investment_products(id) ON DELETE SET NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS investment_operations (
            id TEXT PRIMARY KEY,
            investment_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            operation_type TEXT NOT NULL, -- 'aplicacao', 'reforco', 'resgate_parcial', 'resgate_total', 'juros_dividendo', 'ajuste_cotacao', 'vencimento'
            amount_minor INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'AOA',
            operation_date TEXT NOT NULL,
            description TEXT,
            transaction_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (investment_id) REFERENCES user_investments(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS investment_notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            investment_id TEXT,
            type TEXT NOT NULL, -- 'vencimento_proximo', 'vencimento_liquidado', 'rendimento_creditado', 'atualizacao_mercado', 'alerta_risco'
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (investment_id) REFERENCES user_investments(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_invest_user ON user_investments(user_id);
        CREATE INDEX IF NOT EXISTS idx_invest_ops_user ON investment_operations(user_id);
        CREATE INDEX IF NOT EXISTS idx_invest_notif_user ON investment_notifications(user_id);
        """)

        # Catálogo inicial de produtos de investimento
        produtos_iniciais = [
            (
                "DP-BANKAO-MAX",
                "Depósito a Prazo Super Rendimento BankAO",
                "deposito_prazo",
                "BankAO",
                "open_banking",
                "AOA",
                18.5,
                12,
                10000000, # 100.000 AOA
                "baixo",
                "no_vencimento",
                "Isento de comissões de abertura, manutenção e custódia.",
                "Capital 100% garantido. Resgate antecipado sujeito a penalização de 35% dos juros corridos.",
                "O depósito a prazo com maior rendimento anual do mercado bancário nacional. Ideal para maximizar poupanças com retorno fixo garantido pelo Fundo de Garantia de Depósitos (FGD).",
                1.0
            ),
            (
                "DP-BFA-CRESCENTE",
                "Depósito Trimestral Crescente BFA",
                "deposito_prazo",
                "Banco BFA",
                "open_banking_angola",
                "AOA",
                15.0,
                3,
                5000000, # 50.000 AOA
                "baixo",
                "trimestral",
                "Sem comissões de custódia.",
                "Liquidez trimestral com opção de renovação automática e capitalização de juros.",
                "Depósito de curto prazo com pagamento trimestral de juros para reinvestimento contínuo ou disponibilidade periódica de liquidez.",
                1.0
            ),
            (
                "DP-STDBK-USD",
                "Depósito Moeda Estrangeira USD Standard Bank",
                "deposito_prazo",
                "Standard Bank Angola",
                "open_banking_angola",
                "USD",
                4.5,
                12,
                100000, # 1.000 USD
                "baixo",
                "no_vencimento",
                "Comissão de manutenção de 0.1% a.a. inclusa na taxa líquida.",
                "Resgate no vencimento. Manutenção em moeda forte com cobertura cambial integral.",
                "Rentabilize a sua carteira em dólares com taxa de juro fixa competitiva num dos bancos com maior solidez do continente.",
                1.0
            ),
            (
                "BODIVA-OT-2027",
                "Obrigações do Tesouro OT-NR 2027",
                "obrigacoes",
                "BODIVA / MinFin",
                "bodiva_feed",
                "AOA",
                17.2,
                24,
                25000000, # 250.000 AOA
                "baixo",
                "diaria",
                "Comissão de corretagem BODIVA: 0.25% sobre o valor nominal negociado.",
                "Negociável em mercado secundário da BODIVA a qualquer momento com liquidação T+2.",
                "Títulos de dívida soberana de médio prazo emitidos pela República de Angola com cupão semestral e garantia do Tesouro Nacional.",
                100.0
            ),
            (
                "BODIVA-BT-364",
                "Bilhetes do Tesouro BT 364 Dias",
                "obrigacoes",
                "BODIVA / MinFin",
                "bodiva_feed",
                "AOA",
                16.4,
                12,
                10000000, # 100.000 AOA
                "baixo",
                "no_vencimento",
                "Isento de comissão de corretagem na subscrição primária.",
                "Reembolso de 100% do valor facial no vencimento.",
                "Investimento soberano de curto prazo com taxa de desconto pré-fixada, ideal para reservas institucionais e tesouraria pessoal segura.",
                100.0
            ),
            (
                "ETF-VWCE-GLOBAL",
                "Vanguard FTSE All-World UCITS ETF (VWCE)",
                "etf",
                "Vanguard / Interactive Brokers",
                "global_broker_api",
                "USD",
                10.2,
                None,
                5000, # 50 USD
                "moderado",
                "diaria",
                "TER (Total Expense Ratio): 0.22% ao ano retido diretamente no fundo.",
                "Negociação contínua durante o horário de funcionamento das principais bolsas mundiais.",
                "Exposição direta a mais de 3.800 empresas cotadas em países desenvolvidos e emergentes. Dividendos automaticamente reinvestidos para crescimento composto.",
                128.40
            ),
            (
                "ETF-CSPX-SP500",
                "iShares Core S&P 500 UCITS ETF (CSPX)",
                "etf",
                "BlackRock / Saxo Bank",
                "global_broker_api",
                "USD",
                12.8,
                None,
                10000, # 100 USD
                "moderado",
                "diaria",
                "TER: 0.07% ao ano. Cotação em tempo real.",
                "Venda e resgate instantâneo em dias úteis com liquidação em carteira USD.",
                "Replicação física das 500 maiores corporações dos Estados Unidos da América (Apple, Microsoft, Nvidia, Amazon, Alphabet e outras).",
                542.15
            ),
            (
                "FII-ATLANTICO",
                "Fundo de Investimento Imobiliário Atlântico",
                "fundos",
                "Banco Atlântico Gestão de Ativos",
                "open_banking_angola",
                "AOA",
                14.8,
                36,
                20000000, # 200.000 AOA
                "moderado",
                "trimestral",
                "Comissão de gestão: 1.2% ao ano sobre o património líquido.",
                "Distribuição trimestral de rendas e resgate programado no fecho do exercício.",
                "Portfólio de imóveis de escritórios e logística prime em Luanda e Benguela. Geração estável de fluxo de caixa com proteção contra a inflação.",
                1050.0
            ),
            (
                "FND-BAI-LIQUIDEZ",
                "Fundo de Liquidez e Tesouraria BAI",
                "fundos",
                "BAI Gestão de Ativos",
                "open_banking_angola",
                "AOA",
                16.6,
                None,
                2500000, # 25.000 AOA
                "baixo",
                "diaria",
                "Comissão de gestão reduzida de 0.75% a.a.",
                "Resgate em 24h úteis sem perda de rendimentos capitalizados.",
                "Fundo monetário investido maioritariamente em instrumentos do mercado interbancário e títulos do Tesouro de curtíssimo prazo.",
                1.0
            )
        ]

        for p in produtos_iniciais:
            conn.execute("""
            INSERT OR IGNORE INTO investment_products (
                id, name, category, institution, provider_api, currency, rate_annual,
                term_months, min_amount_minor, risk_level, liquidity, fees_info,
                redemption_conditions, description, current_price, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, p)

        # ──────────────────────────────────────────────────────────────────────
        # Módulo de Cartões
        # ──────────────────────────────────────────────────────────────────────
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            card_type TEXT NOT NULL DEFAULT 'debit',   -- 'debit', 'credit', 'virtual'
            network TEXT NOT NULL DEFAULT 'multicaixa', -- 'visa', 'mastercard', 'multicaixa'
            last_four TEXT NOT NULL,
            cardholder_name TEXT NOT NULL,
            expires_month INTEGER NOT NULL,
            expires_year INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',      -- 'active', 'blocked', 'cancelled'
            is_virtual INTEGER NOT NULL DEFAULT 0,
            is_single_use INTEGER NOT NULL DEFAULT 0,
            label TEXT,
            color_scheme TEXT DEFAULT 'blue',
            online_payments INTEGER DEFAULT 1,
            international_payments INTEGER DEFAULT 1,
            atm_withdrawals INTEGER DEFAULT 1,
            contactless INTEGER DEFAULT 1,
            daily_limit_minor INTEGER DEFAULT 50000000,    -- 500 000 AOA
            monthly_limit_minor INTEGER DEFAULT 200000000, -- 2 000 000 AOA
            daily_spent_minor INTEGER DEFAULT 0,
            monthly_spent_minor INTEGER DEFAULT 0,
            credit_limit_minor INTEGER DEFAULT 0,
            credit_used_minor INTEGER DEFAULT 0,
            currency TEXT DEFAULT 'AOA',
            institution TEXT DEFAULT 'BankAO',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS card_movements (
            id TEXT PRIMARY KEY,
            card_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            amount_minor INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'AOA',
            merchant_name TEXT,
            merchant_category TEXT DEFAULT 'outros',
            merchant_logo TEXT,
            operation_type TEXT NOT NULL DEFAULT 'compra', -- 'compra', 'levantamento', 'reembolso', 'pagamento', 'taxa'
            status TEXT NOT NULL DEFAULT 'completed',      -- 'completed', 'pending', 'reversed', 'failed'
            description TEXT,
            is_debit INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS card_notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            card_id TEXT,
            type TEXT NOT NULL,   -- 'transacao', 'controlo', 'limite', 'suspeita', 'virtual_criado'
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id);
        CREATE INDEX IF NOT EXISTS idx_card_mvt_card ON card_movements(card_id);
        CREATE INDEX IF NOT EXISTS idx_card_notif_user ON card_notifications(user_id);
        """)

        # Seed: criar cartão de débito BankAO para utilizadores que ainda não têm cartão
        import random as _rnd
        try:
            users_sem_cartao = conn.execute("""
                SELECT u.id, u.nome, a.id as account_id, a.currency
                FROM users u
                JOIN accounts a ON a.user_id = u.id AND a.currency = 'AOA'
                WHERE NOT EXISTS (SELECT 1 FROM cards c WHERE c.user_id = u.id)
            """).fetchall()
            for u in users_sem_cartao:
                card_id = str(__import__('uuid').uuid4())
                last_four = str(_rnd.randint(1000, 9999))
                conn.execute("""
                    INSERT OR IGNORE INTO cards (
                        id, user_id, account_id, card_type, network, last_four,
                        cardholder_name, expires_month, expires_year, status,
                        is_virtual, color_scheme, institution
                    ) VALUES (?, ?, ?, 'debit', 'multicaixa', ?, ?, ?, ?, 'active', 0, 'blue', 'BankAO')
                """, (
                    card_id, u["id"], u["account_id"],
                    last_four,
                    (u["nome"] or "CLIENTE BANKAO").upper(),
                    12, 2028
                ))
        except Exception:
            pass

    conn.close()

    # Garantir que os utilizadores de demonstração com histórico existem em qualquer ambiente (Render / Local)
    try:
        from backend.database.seed import seed_demo_users
        seed_demo_users()
    except Exception as e:
        pass


if __name__ == "__main__":
    init_db()
    print("Base de dados BankAO inicializada com sucesso!")
