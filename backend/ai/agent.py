"""
Agente do Copilot (modelo primeiro).

Em vez de uma cadeia de regras que responde "de cor", o modelo lê o pedido, decide que
ferramentas usar (várias voltas, se for preciso) e só depois responde. As ações
(meta, despesa, transferência, depósito) são sempre apenas PREPARADAS: o utilizador confirma
no formulário. Os números vêm sempre das ferramentas, nunca do modelo.
"""
import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.ai.context import get_user_session, update_user_session
from backend.ai.prompts import SYSTEM_PROMPT
from backend.ai.tools.registry import BANKAO_TOOLS_DEFINITIONS, execute_tool
from backend.core.config import settings
from backend.database import get_connection

logger = logging.getLogger("bankao.ai.agent")

MAX_TOOL_ROUNDS = 6
MAX_HISTORY = 16
MAX_TOOL_RESULT_CHARS = 6000

_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_ACTION_TOOLS = {"prepare_savings_goal", "prepare_expense", "prepare_transfer", "prepare_deposit", "prepare_investment"}

_VIEW_NAMES = {
    "view-home": "Início", "view-ops": "Operações", "view-cards": "Cartões", "view-expenses": "Despesas",
    "view-savings": "Poupança", "view-investments": "Investimentos", "view-statement": "Extrato",
    "view-accounts": "Contas", "view-payments": "Pagamentos", "view-copilot": "Copilot",
}

# O modelo nunca pode afirmar que concluiu algo — quem conclui é o cliente.
_DONE_CLAIM = re.compile(
    r"\b(?:j[aá]\s+)?(?:criei|registei|transferi|enviei|depositei|efetuei|efectuei|conclu[ií]|"
    r"foi\s+(?:criada|registada|enviada|transferida|efetuada|efectuada))\b", re.I)
_NEGATION = re.compile(r"\b(?:n[aã]o|ainda|falta|por\s+confirmar|para\s+(?:rever|confirmar))\b", re.I)


# ---------------------------------------------------------------------------
# Contexto dinâmico
# ---------------------------------------------------------------------------
def _customer_brief(user_id: str) -> Dict[str, Any]:
    brief: Dict[str, Any] = {"name": None, "notes": {}}
    try:
        with get_connection() as conn:
            u = conn.execute("SELECT nome, primeiro_nome FROM users WHERE id=?", (user_id,)).fetchone()
            if u:
                name = (u["primeiro_nome"] or u["nome"] or "").strip()
                brief["name"] = None if name in ("", "Novo Utilizador") else name
            rows = conn.execute(
                "SELECT memory_key, memory_value FROM copilot_memory WHERE user_id=? "
                "ORDER BY updated_at DESC LIMIT 10", (user_id,)).fetchall()
            brief["notes"] = {r["memory_key"]: r["memory_value"] for r in rows}
            if brief["notes"].get("nome_preferido"):
                brief["name"] = brief["notes"]["nome_preferido"]
    except Exception as e:  # o contexto é um extra; nunca deve impedir a resposta
        logger.warning("Contexto do cliente indisponível: %s", e)
    return brief


def build_system_prompt(user_id: str, session: Dict[str, Any], client_context: Optional[Dict[str, Any]]) -> str:
    """Prompt base + preferências do cliente (Definições → Copilot IA)."""
    base = _build_system_prompt_base(user_id, session, client_context)
    try:
        from backend.services.user_settings import get_settings
        st = get_settings(user_id)
    except Exception:
        return base
    extra = ["", "═══ PREFERÊNCIAS DO CLIENTE (Definições) ═══"]
    if st.get("ai_language") == "en":
        extra.append("Responde sempre em inglês (English).")
    extra.append({"curto": "Respostas curtas e diretas.", "detalhado": "Respostas detalhadas, com explicação.",
                  }.get(st.get("ai_style"), "Respostas equilibradas."))
    nomes = {"balances": "saldos", "transactions": "movimentos", "cards": "cartões", "savings": "poupanças", "investments": "investimentos"}
    negados = [n for k, n in nomes.items() if not st.get("ai_perm_" + k)]
    if negados:
        extra.append("O cliente NÃO autorizou o acesso do Copilot a: " + ", ".join(negados) +
                     ". Não uses ferramentas nem reveles dados dessas áreas; diz que pode ativar a permissão em Definições → Copilot IA.")
    return base + "\n".join(extra)


def _build_system_prompt_base(user_id: str, session: Dict[str, Any], client_context: Optional[Dict[str, Any]]) -> str:
    today = datetime.date.today()
    lines = [SYSTEM_PROMPT.strip(), "", "═══ CONTEXTO DESTA CONVERSA ═══",
             f"• Hoje: {_WEEKDAYS[today.weekday()]}, {today.isoformat()} (use esta data para 'hoje', 'ontem', 'este mês', 'daqui a 6 meses')."]
    brief = _customer_brief(user_id)
    if brief["name"]:
        lines.append(f"• Cliente: {brief['name']} (usa o nome só se soar natural; não o repitas em todas as respostas).")
    if brief["notes"]:
        notes = "; ".join(f"{k}: {v}" for k, v in brief["notes"].items())
        lines.append(f"• Coisas que o cliente já contou (só usa se ajudarem ao pedido atual): {notes}")
    view = (client_context or {}).get("current_view")
    if view:
        lines.append(f"• Ecrã aberto: {_VIEW_NAMES.get(view, view)} (apenas contexto; não faças nada só por isso).")
    last = session.get("last_action")
    if last:
        lines.append("• Última ação que PREPARASTE e que o cliente ainda pode ter aberta (se ele pedir uma alteração, "
                     f"prepara de novo com os dados corrigidos): {json.dumps(last, ensure_ascii=False)}")
    return "\n".join(lines)


def _clean_history(history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for h in (history or [])[-MAX_HISTORY:]:
        role = h.get("role") if isinstance(h, dict) else None
        content = h.get("content") if isinstance(h, dict) else None
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            out.append({"role": role, "content": content.strip()[:1500]})
    return out


# ---------------------------------------------------------------------------
# Pós-processamento
# ---------------------------------------------------------------------------
def _clean_reply(text: str, action_prepared: bool) -> str:
    text = re.sub(r"```.*?```", "", text or "", flags=re.DOTALL).strip()
    text = re.sub(r"<\s*/?\s*(?:tool_call|function_call)[^>]*>", "", text).strip()
    # frases em que o modelo afirma ter concluído algo (sem negação) levam a correção honesta
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if _DONE_CLAIM.search(sentence) and not _NEGATION.search(sentence):
            suffix = ("Ainda **não foi concluído**: toque no botão do cartão para rever e confirmar."
                      if action_prepared else
                      "Não consigo concluir operações por si: preparo os dados e é você quem confirma no formulário.")
            return f"{text}\n\n{suffix}"
    return text


def _assistant_message_dict(msg: Any) -> Dict[str, Any]:
    calls = []
    for tc in getattr(msg, "tool_calls", None) or []:
        calls.append({
            "id": tc.id,
            "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
        })
    return {"role": "assistant", "content": getattr(msg, "content", None) or "", "tool_calls": calls}


def _trim(result: Dict[str, Any]) -> str:
    raw = json.dumps(result, ensure_ascii=False, default=str)
    return raw if len(raw) <= MAX_TOOL_RESULT_CHARS else raw[:MAX_TOOL_RESULT_CHARS] + "…[cortado]"


# ---------------------------------------------------------------------------
# Ciclo principal
# ---------------------------------------------------------------------------
def run_agent(
    client: Any,
    user_id: str,
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    client_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Corre o agente. Devolve o dicionário de resposta, ou None se o modelo não produziu nada útil.
    Deixa propagar exceções de rede/modelo para o chamador decidir (repetir ou usar o plano B).
    """
    session = get_user_session(user_id)
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(user_id, session, client_context)},
        *_clean_history(history),
        {"role": "user", "content": message},
    ]

    tools_used: List[str] = []
    action: Optional[Dict[str, Any]] = None
    chart: Optional[Dict[str, Any]] = None
    fallback_summary: Optional[str] = None
    final_text = ""

    for round_no in range(MAX_TOOL_ROUNDS + 1):
        allow_tools = round_no < MAX_TOOL_ROUNDS
        kwargs: Dict[str, Any] = dict(model=settings.MODEL_NAME, messages=messages, max_tokens=2500, temperature=0.2, timeout=40)
        if allow_tools:
            kwargs.update(tools=BANKAO_TOOLS_DEFINITIONS, tool_choice="auto")
        response = client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        calls = getattr(msg, "tool_calls", None) if allow_tools else None

        if not calls:
            final_text = (getattr(msg, "content", None) or "").strip()
            break

        messages.append(_assistant_message_dict(msg))
        for tc in calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                if not isinstance(args, dict):
                    args = {}
            except Exception:
                args = {}
            tools_used.append(name)
            result = execute_tool(name, args, user_id=user_id)

            if name in _ACTION_TOOLS:
                if result.get("ok") and result.get("action"):
                    action = result["action"]
                    fallback_summary = result.get("summary")
                else:
                    # uma tentativa falhada não pode deixar ficar um cartão antigo da mesma conversa
                    action = None
            if isinstance(result.get("chart"), dict):
                chart = result["chart"]
                result = {k: v for k, v in result.items() if k != "chart"}
                result["chart_shown_to_user"] = True

            messages.append({"role": "tool", "tool_call_id": tc.id, "name": name, "content": _trim(result)})

    if not final_text and fallback_summary:
        final_text = fallback_summary  # o modelo calou-se, mas a ferramenta já tem um resumo honesto
    if not final_text:
        return None

    acted = any(t in _ACTION_TOOLS for t in tools_used)
    update_user_session(user_id, {
        "last_action": action if acted else session.get("last_action"),
        "last_tool_used": tools_used[-1] if tools_used else None,
        "pending_operation": None,
    })

    return {
        "reply": _clean_reply(final_text, action is not None),
        "action": action,
        "pending": None,
        "chart": chart,
        "tools_used": tools_used,
        "requires_confirmation": action is not None,
        "model": settings.MODEL_NAME,
        "provider": "BankAO Copilot",
    }
