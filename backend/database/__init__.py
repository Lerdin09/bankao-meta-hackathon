"""Base de dados SQLite: ligação, transações e criação do esquema."""
from backend.database.connection import DB_PATH, get_connection, transaction_scope
from backend.database.schema import init_db

__all__ = ["DB_PATH", "get_connection", "transaction_scope", "init_db"]
