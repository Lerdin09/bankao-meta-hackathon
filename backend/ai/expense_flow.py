# -*- coding: utf-8 -*-
"""
Despesas no Copilot: REGISTO DIRETO e REMOÇÃO por descrição detalhada.

• Registo: «comprei um telefone de 22 mil» grava logo a despesa (Telefone · 22.000 Kz · Eletrónicos · hoje),
  sem formulário nem pergunta de confirmação. Só se pergunta quando falta o valor.
• Remoção: «remove a despesa do telefone que comprei ontem a 22 mil» apaga essa despesa. Só apaga quando o pedido
  é detalhado (pelo menos 2 de: nome, valor, dia) e corresponde a UMA despesa; se faltar detalhe ou houver mais do
  que uma candidata, mostra as candidatas e pede o que falta (nunca apaga «à sorte»).

Uma despesa é só um registo (não mexe no saldo). As criadas por poupanças, transferências ou investimentos
representam dinheiro que realmente se moveu: essas o Copilot não remove.
"""
import logging
import re
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from backend.ai.intents import QUESTION_START, _blank, _norm, _parse_slots, fmt_money, normalize_spoken_text
from backend.database import get_connection
from backend.database.connection import transaction_scope
from backend.schemas.finance import CATEGORIAS as DB_CATEGORIAS

logger = logging.getLogger("bankao.ai.expense_flow")

KIND = "DELETE_EXPENSE"
_PROTECTED_ORIGINS = ("savings", "transfer", "investment")
_ORIGIN_LABEL = {"savings": "uma poupança", "transfer": "uma transferência", "investment": "um investimento"}


# ---------------------------------------------------------------------------
# Registo direto
# ---------------------------------------------------------------------------
def _category(cat: Optional[str]) -> str:
    if cat == "Investimento":
        cat = "Investimentos"
    return cat if cat in DB_CATEGORIAS else "Outros"


def _row_to_dict(r) -> Dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "category": r["category"], "amount": r["amount_minor"] / 100.0,
            "currency": r["currency"], "date": r["expense_date"], "origin": r["origin"], "notes": r["notes"] or ""}


def _when(iso: str, today: date) -> str:
    if iso == today.isoformat():
        return "hoje"
    if iso == (today - timedelta(days=1)).isoformat():
        return "ontem"
    return "/".join(reversed(iso.split("-")))


def register_expense(user_id: str, action: Dict[str, Any], today: Optional[date] = None) -> Dict[str, Any]:
    """Grava a despesa já. Um segundo pedido igual em <60 s (voz repetida, duplo toque) não duplica."""
    today = today or date.today()
    name = (action.get("name") or "").strip()[:120] or "Despesa"
    cat = _category(action.get("category"))
    minor = int(round(float(action["amount"]) * 100))
    iso = str(action.get("date") or today.isoformat())[:10]
    with transaction_scope() as conn:
        dup = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? AND name = ? AND amount_minor = ? AND expense_date = ? "
            "AND origin = 'ai' AND created_at >= datetime('now', '-60 seconds')",
            (user_id, name, minor, iso)).fetchone()
        if dup:
            return {"expense": _row_to_dict(dup), "duplicate": True}
        exp_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO expenses (id, user_id, name, category, amount_minor, currency, expense_date, origin, notes) "
            "VALUES (?, ?, ?, ?, ?, 'AOA', ?, 'ai', ?)",
            (exp_id, user_id, name, cat, minor, iso, "Registado pelo Copilot"))
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (exp_id,)).fetchone()
    return {"expense": _row_to_dict(row), "duplicate": False}


def apply_direct_registration(user_id: str, result: Dict[str, Any], today: Optional[date] = None) -> Dict[str, Any]:
    """
    Se a resposta traz uma despesa «preparada» (REGISTER_EXPENSE), regista-a logo e troca a resposta por uma
    confirmação. Em caso de erro mantém o comportamento antigo (formulário para o cliente rever).
    """
    action = (result or {}).get("action")
    if not isinstance(action, dict) or action.get("type") != "REGISTER_EXPENSE":
        return result
    today = today or date.today()
    try:
        out = register_expense(user_id, action, today)
    except Exception as e:  # noqa: BLE001
        logger.error("Registo direto da despesa falhou: %s", e, exc_info=True)
        return result
    exp = out["expense"]
    head = "Esta despesa já estava registada" if out["duplicate"] else "Registei a despesa"
    result["reply"] = (f"{head} **{exp['name']}** · **{fmt_money(exp['amount'])}** "
                       f"({exp['category']}, {_when(exp['date'], today)}).\n"
                       "Se foi engano, diga por exemplo «remove a despesa do "
                       f"{_norm(exp['name'])} de {fmt_money(exp['amount'])}».")
    result["action"] = {"type": "EXPENSE_REGISTERED", **exp}
    result["pending"] = None
    result["requires_confirmation"] = False
    tools = list(result.get("tools_used") or [])
    if "expense_register" not in tools:
        tools.append("expense_register")
    result["tools_used"] = tools
    return result


# ---------------------------------------------------------------------------
# Remoção: o que o cliente disse
# ---------------------------------------------------------------------------
# «retirar/tirar/cancelar» ficam de fora de propósito: «retirar 20 mil para compras» é levantar dinheiro, não apagar uma despesa
_DEL_VERB = re.compile(r"\b(?:remov\w*|apag\w*|elimin\w*|delet\w*|exclu\w*|desfaz\w*)\b")
_OTHER_REQUEST = re.compile(r"transfer|\benvi\w*|\bmand\w*|poup\w*|invest\w*|invist\w*|aplic\w*|deposit\w*|\bmeta\b|"
                            r"quanto|\bsaldo\b|extrato|cartao|gastei|paguei|comprei")
_EXP_WORD = re.compile(r"\b(?:despesas?|gastos?|compras?|registos?|lancamentos?)\b")
_HOWTO = re.compile(r"\b(?:como|posso|consigo|podes|e possivel|sera que)\b")
_CANCEL = re.compile(r"\bcancela\w*|\besquece\w*|\bdeixa (?:estar|para la|isso)\b|\bnao (?:quero|precisa)\b|^\W*nao\W*$")

_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
          "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_DATE_NUM = re.compile(r"\b(\d{1,2})\s*[/-]\s*(\d{1,2})(?:\s*[/-]\s*(\d{2,4}))?\b")
_DATE_DIA = re.compile(r"\b(?:no\s+)?dia\s+(\d{1,2})(?:\s+de\s+([a-z]+))?\b")
_DATE_MES = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(_MESES) + r")(?:\s+de\s+(\d{4}))?\b")

_STOP = set("""
a o os as um uma uns umas de do da dos das em no na nos nas ao aos por para com sem que se e ou mas ja so tambem
eu meu minha meus minhas me te lhe nos esse essa isso este esta isto aquele aquela aquilo mesmo mesma
ontem hoje anteontem agora favor pf pode podes poderia quero queria gostava gostaria preciso vamos vai
ultima ultimo primeira primeiro outra outro tal qual quais quanto mil milhao milhoes kz kzs kwanza kwanzas aoa akz
comprei comprado paguei pago gastei gasto fiz fez feita feito registei registado registei adicionei lancei
despesa despesas gasto gastos compra compras registo registos lancamento lancamentos dia mes ano
""".split())


def _is_howto(n: str, text: str) -> bool:
    return text.rstrip().endswith("?") or bool(QUESTION_START.search(n)) or bool(_HOWTO.search(n))


def _safe_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _explicit_date(n: str, today: date) -> tuple:
    """Dia dito por extenso/numérico («dia 3», «3 de novembro», «03/11»): devolve (data|None, n com a data apagada)."""
    spans, found = [], None

    def past(d: Optional[date]) -> Optional[date]:
        if d and d > today:                      # «dia 28» dito a dia 4 → mês passado/ano passado
            return _safe_date(d.year - 1, d.month, d.day)
        return d

    for m in _DATE_MES.finditer(n):
        found = found or past(_safe_date(int(m.group(3) or today.year), _MESES[m.group(2)], int(m.group(1))))
        spans.append(m.span())
    for m in _DATE_NUM.finditer(n):
        yr = int(m.group(3)) if m.group(3) else today.year
        yr += 2000 if yr < 100 else 0
        found = found or past(_safe_date(yr, int(m.group(2)), int(m.group(1))))
        spans.append(m.span())
    for m in _DATE_DIA.finditer(n):
        mon = _MESES.get(m.group(2) or "", today.month)
        found = found or past(_safe_date(today.year, mon, int(m.group(1))))
        spans.append(m.span())
    return found, (_blank(n, spans) if spans else n)


def _parse_request(text: str, today: date) -> Dict[str, Any]:
    text = normalize_spoken_text(text)
    n = _norm(text)
    day, n_nodate = _explicit_date(n, today)
    slots = _parse_slots(n_nodate, today)
    out: Dict[str, Any] = {}
    if slots.get("amount"):
        out["amount"] = float(slots["amount"])
    iso = day.isoformat() if day else slots.get("date")
    if iso:
        out["date"] = iso
    n_kw = n_nodate
    if slots.get("_amount_span"):
        n_kw = _blank(n_kw, [tuple(slots["_amount_span"])])
    words = [w for w in re.findall(r"[a-z]+", n_kw)
             if len(w) >= 3 and w not in _STOP and not _DEL_VERB.fullmatch(w) and w not in _MESES]
    if words:
        out["kw"] = words
    return out


# ---------------------------------------------------------------------------
# Remoção: procurar e apagar
# ---------------------------------------------------------------------------
def _fetch(user_id: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY expense_date DESC, created_at DESC, rowid DESC LIMIT 500",
            (user_id,)).fetchall()
    return [dict(r) for r in rows]


def _kw_score(row: Dict[str, Any], kw: List[str]) -> int:
    """Quantas das palavras ditas aparecem no nome/nota/categoria da despesa."""
    hay = [h for h in re.findall(r"[a-z]+", _norm(f"{row['name']} {row.get('notes') or ''} {row['category']}")) if len(h) >= 3]
    return sum(any(h.startswith(k) or k.startswith(h) for h in hay) for k in kw)


def _matches(rows: List[Dict[str, Any]], slots: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = rows
    if slots.get("amount"):
        minor = int(round(float(slots["amount"]) * 100))
        out = [r for r in out if r["amount_minor"] == minor]
    if slots.get("date"):
        out = [r for r in out if r["expense_date"] == slots["date"]]
    if slots.get("kw"):
        scored = [(_kw_score(r, slots["kw"]), r) for r in out]
        best = max((sc for sc, _ in scored), default=0)
        out = [r for sc, r in scored if sc > 0 and sc == best]   # fica com as que casam melhor com o que foi dito
    return out


def _line(r: Dict[str, Any]) -> str:
    return f"• **{r['name']}** · {fmt_money(r['amount_minor'] / 100.0)} · {_when(r['expense_date'], date.today())}"


def _is_protected(r: Dict[str, Any]) -> bool:
    return bool(r.get("goal_id")) or r.get("origin") in _PROTECTED_ORIGINS


def _state(slots: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": KIND, "slots": slots}


def _ask_detail(user_id: str, slots: Dict[str, Any], rows: List[Dict[str, Any]], intro: str = "") -> Dict[str, Any]:
    given = bool(slots.get("amount") or slots.get("date") or slots.get("kw"))
    cands = [r for r in _matches(rows, slots) if not _is_protected(r)] if given else \
            [r for r in rows if not _is_protected(r)]
    lines = [f"{intro}Para remover uma despesa preciso de ser mais certo: diga o **nome** e o **valor** "
             "(ou o dia). Por exemplo: «remove a despesa do telefone de 22 mil de ontem»."]
    if cands:
        lines += ["", "Candidatas:" if given else "As mais recentes:"] + [_line(r) for r in cands[:5]]
    return {"reply": "\n".join(lines), "action": None, "pending": _state(slots)}


def _delete_row(user_id: str, row: Dict[str, Any]) -> bool:
    with transaction_scope() as conn:
        cur = conn.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (row["id"], user_id))
        return cur.rowcount > 0


def handle_expense_delete(user_id: str, message: str, pending: Optional[Dict[str, Any]] = None,
                          today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """
    Devolve {"reply", "action", "pending"} ou None quando a mensagem não é um pedido para remover uma despesa
    (as outras respostas do Copilot seguem normalmente).
    """
    today = today or date.today()
    text = (message or "").strip()
    if not text:
        return None
    n = _norm(text)
    state = pending if isinstance(pending, dict) and pending.get("type") == KIND else None

    if state is None:
        if not (_DEL_VERB.search(n) and _EXP_WORD.search(n)) or _is_howto(n, text):
            return None
        slots: Dict[str, Any] = {}
    else:
        if _CANCEL.search(n):
            return {"reply": "Sem problema, não removi nada. Em que mais posso ajudar?", "action": None, "pending": None}
        if _is_howto(n, text) or _OTHER_REQUEST.search(n):
            return None                   # pedido novo (transferir, investir, outra despesa…): deixa de ser resposta à remoção
        slots = dict(state.get("slots") or {})

    got = _parse_request(text, today)
    if state is not None and not got:
        return None                       # não trouxe nada que ajude a escolher: segue para o resto do Copilot
    slots.update(got)
    if "kw" in got and state is not None and state.get("slots", {}).get("kw"):
        slots["kw"] = list(dict.fromkeys(list(state["slots"]["kw"]) + got["kw"]))

    rows = _fetch(user_id)
    detail = sum(bool(slots.get(k)) for k in ("kw", "amount", "date"))
    if detail < 2:
        return _ask_detail(user_id, slots, rows)

    found = _matches(rows, slots)
    if not found:
        return {"reply": "Não encontrei nenhuma despesa com esses dados, por isso não removi nada. "
                         "Confirme o nome, o valor e o dia (veja a lista em **Despesas**).",
                "action": None, "pending": _state(slots)}

    deletable = [r for r in found if not _is_protected(r)]
    if not deletable:
        r = found[0]
        why = _ORIGIN_LABEL.get(r.get("origin"), "uma poupança")
        return {"reply": f"A despesa **{r['name']}** foi criada por {why} e representa dinheiro que realmente "
                         "saiu da conta: não a posso remover daqui.", "action": None, "pending": None}

    same = {(r["name"], r["amount_minor"], r["expense_date"], r["category"]) for r in deletable}
    if len(deletable) > 1 and len(same) > 1:
        return {"reply": "Encontrei mais do que uma despesa assim. Diga qual (acrescente o dia ou o nome exato):\n\n"
                         + "\n".join(_line(r) for r in deletable[:6]),
                "action": None, "pending": _state(slots)}

    row = deletable[0]                    # várias iguais: apaga só a mais recente
    if not _delete_row(user_id, row):
        return {"reply": "Não consegui remover essa despesa agora. Tente outra vez daqui a pouco.",
                "action": None, "pending": None}
    extra = f" (havia {len(deletable)} iguais; removi só a mais recente)" if len(deletable) > 1 else ""
    return {"reply": f"Removi a despesa **{row['name']}** · **{fmt_money(row['amount_minor'] / 100.0)}** "
                     f"({row['category']}, {_when(row['expense_date'], today)}){extra}.",
            "action": {"type": "EXPENSE_DELETED", "id": row["id"], "name": row["name"],
                       "amount": row["amount_minor"] / 100.0, "date": row["expense_date"]},
            "pending": None}
