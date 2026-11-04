"""
Definições do utilizador: preferências (JSON validado), sessões/dispositivos,
histórico de acessos e limites diários.

Dados sensíveis (IBAN, nº de conta, NIF/nº do documento, tipo de documento, KYC)
NUNCA são alteráveis por aqui: só existem em modo leitura.
"""
import datetime
import json
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException

from backend.database import get_connection

# Chaves que nunca podem ser escritas por este módulo
PROTEGIDOS = {"iban", "iban_virtual", "account_number", "numero_conta", "nif", "doc_numero",
              "doc_tipo", "data_emissao", "kyc_status", "nome", "primeiro_nome", "ultimo_nome"}

# Valores por omissão + validação: (tipo, opções | (min, max))
SCHEMA: Dict[str, Dict[str, Any]] = {
    # Segurança
    "biometric": {"default": False, "type": "bool"},
    "twofa": {"default": False, "type": "bool"},
    # Notificações
    "n_transfers": {"default": True, "type": "bool"},
    "n_payments": {"default": True, "type": "bool"},
    "n_received": {"default": True, "type": "bool"},
    "n_card": {"default": True, "type": "bool"},
    "n_movements": {"default": False, "type": "bool"},
    "n_low_balance": {"default": True, "type": "bool"},
    "n_low_balance_threshold": {"default": 50000, "type": "num", "range": (0, 1_000_000_000)},
    "n_promos": {"default": False, "type": "bool"},
    "ch_push": {"default": True, "type": "bool"},
    "ch_sms": {"default": True, "type": "bool"},
    "ch_email": {"default": False, "type": "bool"},
    # Preferências
    "language": {"default": "pt", "type": "enum", "options": ["pt", "en"]},
    "currency": {"default": "AOA", "type": "enum", "options": ["AOA", "EUR", "USD"]},
    "date_format": {"default": "DD/MM/AAAA", "type": "enum", "options": ["DD/MM/AAAA", "MM/DD/AAAA", "AAAA-MM-DD"]},
    "number_format": {"default": "1 234,56", "type": "enum", "options": ["1.234,56", "1 234,56", "1,234.56"]},
    "theme": {"default": "dark", "type": "enum", "options": ["dark", "light", "system"]},
    "home_page": {"default": "view-home", "type": "enum",
                  "options": ["view-home", "view-accounts", "view-payments", "view-savings", "view-expenses", "view-statement"]},
    "hide_balances": {"default": True, "type": "bool"},
    # Contas e cartões
    "main_account_id": {"default": "", "type": "str"},
    "online_payments": {"default": True, "type": "bool"},
    "limit_withdraw": {"default": 200000, "type": "num", "range": (0, 1_000_000_000)},
    "limit_payments": {"default": 1000000, "type": "num", "range": (0, 1_000_000_000)},
    "limit_transfers": {"default": 2000000, "type": "num", "range": (0, 1_000_000_000)},
    # Copilot
    "ai_enabled": {"default": True, "type": "bool"},
    "ai_voice": {"default": True, "type": "bool"},
    "ai_read_aloud": {"default": False, "type": "bool"},
    "ai_language": {"default": "pt", "type": "enum", "options": ["pt", "en"]},
    "ai_confirm": {"default": True, "type": "bool"},
    "ai_style": {"default": "equilibrado", "type": "enum", "options": ["curto", "equilibrado", "detalhado"]},
    "ai_perm_balances": {"default": True, "type": "bool"},
    "ai_perm_transactions": {"default": True, "type": "bool"},
    "ai_perm_cards": {"default": True, "type": "bool"},
    "ai_perm_savings": {"default": False, "type": "bool"},
    "ai_perm_investments": {"default": False, "type": "bool"},
}


def ensure_tables() -> None:
    with get_connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY, data TEXT NOT NULL DEFAULT '{}', pin_hash TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS user_sessions (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, device TEXT, ip TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            revoked INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, device TEXT, ip TEXT,
            success INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS support_requests (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, message TEXT,
            status TEXT DEFAULT 'aberto', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        """)


def defaults() -> Dict[str, Any]:
    return {k: v["default"] for k, v in SCHEMA.items()}


def get_settings(user_id: str) -> Dict[str, Any]:
    ensure_tables()
    with get_connection() as c:
        row = c.execute("SELECT data FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    out = defaults()
    if row:
        try:
            saved = json.loads(row["data"] or "{}")
            out.update({k: v for k, v in saved.items() if k in SCHEMA})
        except ValueError:
            pass
    return out


def validate(patch: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for key, val in patch.items():
        if key.lower() in PROTEGIDOS:
            raise HTTPException(400, f"«{key}» é um dado sensível e não pode ser alterado nas definições.")
        spec = SCHEMA.get(key)
        if not spec:
            raise HTTPException(400, f"Definição desconhecida: {key}.")
        t = spec["type"]
        if t == "bool":
            if not isinstance(val, bool):
                raise HTTPException(400, f"Valor inválido para {key}.")
        elif t == "enum":
            if val not in spec["options"]:
                raise HTTPException(400, f"Valor inválido para {key}.")
        elif t == "num":
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise HTTPException(400, f"Valor inválido para {key}.")
            lo, hi = spec["range"]
            if not (lo <= val <= hi):
                raise HTTPException(400, f"{key} fora do intervalo permitido.")
        elif t == "str":
            if not isinstance(val, str) or len(val) > 64:
                raise HTTPException(400, f"Valor inválido para {key}.")
        clean[key] = val
    return clean


def save_settings(user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    clean = validate(patch)
    if "main_account_id" in clean and clean["main_account_id"]:
        with get_connection() as c:
            ok = c.execute("SELECT 1 FROM accounts WHERE id = ? AND user_id = ?",
                           (clean["main_account_id"], user_id)).fetchone()
        if not ok:
            raise HTTPException(400, "Conta principal inválida.")
    cur = get_settings(user_id)
    cur.update(clean)
    with get_connection() as c:
        c.execute("""INSERT INTO user_settings (user_id, data, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                     ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = CURRENT_TIMESTAMP""",
                  (user_id, json.dumps(cur)))
    return cur


# ---------- Sessões / histórico ----------
def create_session(user_id: str, device: str = "", ip: str = "") -> str:
    ensure_tables()
    sid = str(uuid.uuid4())
    with get_connection() as c:
        c.execute("INSERT INTO user_sessions (id, user_id, device, ip) VALUES (?, ?, ?, ?)",
                  (sid, user_id, (device or "Dispositivo desconhecido")[:200], ip))
        c.execute("INSERT INTO login_history (user_id, device, ip, success) VALUES (?, ?, ?, 1)",
                  (user_id, (device or "")[:200], ip))
    return sid


def log_failed_login(user_id: str, device: str = "", ip: str = "") -> None:
    ensure_tables()
    with get_connection() as c:
        c.execute("INSERT INTO login_history (user_id, device, ip, success) VALUES (?, ?, ?, 0)",
                  (user_id, (device or "")[:200], ip))


def session_is_revoked(sid: Optional[str]) -> bool:
    if not sid:
        return False
    with get_connection() as c:
        row = c.execute("SELECT revoked FROM user_sessions WHERE id = ?", (sid,)).fetchone()
        if row is None:
            return False
        if not row["revoked"]:
            c.execute("UPDATE user_sessions SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (sid,))
        return bool(row["revoked"])


# ---------- Limites diários ----------
def _to_aoa_factor(conn, currency: str) -> float:
    if currency == "AOA":
        return 1.0
    r = conn.execute("SELECT rate FROM fx_rates WHERE base_currency = ? AND quote_currency = 'AOA'", (currency,)).fetchone()
    if r and r["rate"]:
        return float(r["rate"])
    r = conn.execute("SELECT rate FROM fx_rates WHERE base_currency = 'AOA' AND quote_currency = ?", (currency,)).fetchone()
    if r and r["rate"]:
        return 1.0 / float(r["rate"])
    return 1.0


def check_transfer_limit(user_id: str, from_account_id: str, amount_minor: int) -> None:
    """Rejeita a transferência se o total do dia (em Kz) exceder o limite definido."""
    limit = float(get_settings(user_id)["limit_transfers"])
    if limit <= 0:
        return
    with get_connection() as c:
        acc = c.execute("SELECT currency FROM accounts WHERE id = ? AND user_id = ?", (from_account_id, user_id)).fetchone()
        if not acc:
            return
        rows = c.execute("""SELECT t.source_amount_minor AS amt, t.source_currency AS cur FROM transfers t
                            JOIN accounts a ON a.id = t.from_account_id
                            WHERE a.user_id = ? AND t.status != 'failed' AND date(t.created_at) = date('now')""",
                         (user_id,)).fetchall()
        used = sum(r["amt"] / 100.0 * _to_aoa_factor(c, r["cur"]) for r in rows)
        this = amount_minor / 100.0 * _to_aoa_factor(c, acc["currency"])
    if used + this > limit + 0.005:
        left = max(0.0, limit - used)
        raise HTTPException(400, f"Limite diário de transferências excedido ({limit:,.0f} Kz). Ainda pode transferir {left:,.0f} Kz hoje.".replace(",", " "))
