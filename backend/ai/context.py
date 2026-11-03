"""
Gestor de Contexto Conversacional e Continuidade Multi-Turn para a IA do BankAO.
Rastreia tópico ativo, período em discussão, entidade/categoria e operações pendentes.
Expira automaticamente após 15 minutos de inatividade para segurança.
"""
import datetime
import re
import time
from typing import Any, Dict, List, Optional


# Contexto em memória por utilizador (isolamento estrito)
_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_EXPIRY_SECONDS = 900  # 15 minutos


def get_user_session(user_id: str) -> Dict[str, Any]:
    """Retorna a sessão conversacional ativa do utilizador, criando uma nova se expirada."""
    now = time.time()
    session = _SESSIONS.get(user_id)

    if not session or (now - session.get("updated_at", 0) > SESSION_EXPIRY_SECONDS):
        session = {
            "user_id": user_id,
            "active_topic": None,         # 'expenses', 'incomes', 'accounts', 'transfers', 'cards', 'investments'
            "active_category": None,      # ex: 'Restaurantes', 'Alimentação'
            "active_period": None,        # 'this_month', 'last_month', 'last_3_months'
            "active_currency": "AOA",
            "pending_operation": None,    # {type, slots, ask}
            "last_tool_used": None,
            "created_at": now,
            "updated_at": now
        }
        _SESSIONS[user_id] = session

    return session


def update_user_session(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atualiza os campos da sessão conversacional ativa."""
    session = get_user_session(user_id)
    session.update(updates)
    session["updated_at"] = time.time()
    _SESSIONS[user_id] = session
    return session


def clear_user_session(user_id: str) -> None:
    """Limpa a sessão conversacional do utilizador."""
    _SESSIONS.pop(user_id, None)


def detect_follow_up(message: str, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Deteta se a mensagem é uma pergunta de seguimento elíptica (ex: 'E no mês passado?',
    'E em restaurantes?', 'E na conta em dólares?', '50 mil').
    Retorna os parâmetros resolvidos combinando o contexto anterior.
    """
    m = message.strip().lower()
    active_topic = session.get("active_topic")

    # 1. Seguimento de período (ex: "e no mês passado?", "e no mês anterior?", "e este mês?")
    m_period = re.search(r"^(?:e\s+)?(?:no\s+m[eê]s\s+passado|no\s+m[eê]s\s+anterior|no\s+passado|m[eê]s\s+passado)\??$", m)
    if m_period:
        if active_topic in ("expenses", "incomes"):
            return {
                "type": "period_shift",
                "topic": active_topic,
                "period": "last_month",
                "category": session.get("active_category")
            }

    m_this_month = re.search(r"^(?:e\s+)?(?:este\s+m[eê]s|no\s+m[eê]s\s+atual)\??$", m)
    if m_this_month:
        if active_topic in ("expenses", "incomes"):
            return {
                "type": "period_shift",
                "topic": active_topic,
                "period": "this_month",
                "category": session.get("active_category")
            }

    # 2. Seguimento de categoria de despesa (ex: "e em restaurantes?", "e com supermercado?", "e em transporte?")
    m_cat = re.search(r"^(?:e\s+)?(?:em\s+|com\s+|para\s+)?(restaurantes?|alimenta[cç][aã]o|supermercado|transporte|t[aá]xi|lazer|sa[uú]de|combust[ií]vel)\??$", m)
    if m_cat and active_topic == "expenses":
        cat_word = m_cat.group(1)
        mapped = "Restaurantes" if "restaurante" in cat_word else \
                 "Alimentação" if "alimenta" in cat_word or "supermercado" in cat_word else \
                 "Transporte" if "transporte" in cat_word or "taxi" in cat_word or "combustivel" in cat_word else \
                 cat_word.title()
        return {
            "type": "category_filter",
            "topic": "expenses",
            "period": session.get("active_period") or "this_month",
            "category": mapped
        }

    # 3. Seguimento de moeda de conta (ex: "e em dólares?", "e em euros?", "e na conta usd?")
    # Normalizar para lidar com acentos: dólares/dolares → dolar, euros, etc.
    import unicodedata
    m_normalized = "".join(
        c for c in unicodedata.normalize("NFD", m)
        if unicodedata.category(c) != "Mn"
    )
    m_curr = re.search(r"^(?:e\s+)?(?:em\s+|na\s+conta\s+(?:em\s+)?)?(dolares?|usd|euros?|eur|aoa|kwanzas?)[\?\s]*$", m_normalized)
    if m_curr and (active_topic in ("accounts", None) or "dolar" in m_normalized or "usd" in m_normalized or "euro" in m_normalized):
        cur_word = m_curr.group(1)
        cur = "USD" if "dolar" in cur_word or "usd" in cur_word else \
              "EUR" if "euro" in cur_word or "eur" in cur_word else "AOA"
        return {
            "type": "currency_filter",
            "topic": "accounts",
            "currency": cur
        }

    return None
