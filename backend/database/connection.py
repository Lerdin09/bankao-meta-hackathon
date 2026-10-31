"""
Ligação à base de dados SQLite em modo WAL com integridade transacional.
"""
import sqlite3
from contextlib import contextmanager

from backend.core.config import settings

DB_PATH = str(settings.DB_FILE)


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
