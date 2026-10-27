"""
Camada de Banco de Dados SQLite em modo WAL com integridade transacional.
"""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bankao.db"))

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Ativa modo WAL (Write-Ahead Logging) para alta concorrência e chave estrangeira
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

@contextmanager
def transaction_scope():
    """Gerenciador de contexto para transações imediatas e atômicas."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Inicializa as tabelas do sistema bancário e livro-razão."""
    conn = get_connection()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            telefone TEXT,
            kyc_status TEXT DEFAULT 'verificado', -- 'pendente', 'verificado', 'bloqueado'
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

        -- Índices para performance
        CREATE INDEX IF NOT EXISTS idx_ledger_account ON ledger_entries(account_id);
        CREATE INDEX IF NOT EXISTS idx_ledger_tx ON ledger_entries(transaction_id);
        CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at);
        """)
        
        # Insere taxas de câmbio de referência simuladas caso ainda não existam
        conn.execute("""
        INSERT OR IGNORE INTO fx_rates (base_currency, quote_currency, rate, fee_percentage)
        VALUES 
            ('EUR', 'AOA', 1050.00, 0.015),
            ('AOA', 'EUR', 0.000952, 0.015),
            ('USD', 'AOA', 950.00, 0.015),
            ('AOA', 'USD', 0.001052, 0.015),
            ('EUR', 'USD', 1.08, 0.010),
            ('USD', 'EUR', 0.925, 0.010);
        """)
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Base de dados Bankão inicializada com sucesso!")
