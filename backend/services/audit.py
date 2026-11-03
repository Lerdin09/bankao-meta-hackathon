"""Registo de auditoria (audit_log). Nunca deve partir a operacao principal."""
import json
from typing import Any, Optional

from backend.database import get_connection


def write_audit_log(user_id: Optional[str], action: str, details: Any = None) -> None:
    try:
        text = details if isinstance(details, str) else json.dumps(details, default=str) if details is not None else None
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
                (user_id, action, text),
            )
            conn.commit()
    except Exception:
        pass
