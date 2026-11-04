# -*- coding: utf-8 -*-
"""
Fluxo guiado de INVESTIMENTO do Copilot.

O cliente é guiado pergunta a pergunta: produto → montante → nome do investimento.
Só no fim (ou quando ele pede) abre o formulário de subscrição já preenchido:

  • todas as respostas dadas        → abre o formulário com tudo preenchido
  • «abre o formulário» a meio      → abre o formulário só com o que já foi dito
  • «abre a página de investimentos» → abre apenas a página (sem formulário)

Nunca investe nada: quem carrega em «Confirmar» no formulário é sempre o cliente.
"""
import re
from datetime import date
from typing import Any, Dict, List, Optional

from backend.ai.intents import QUESTION_START, _norm, _parse_slots, fmt_money

KIND = "INVESTMENT_APPLY"
_NET_TAX_CATS = ("deposito_prazo", "obrigacoes")


# ---------------------------------------------------------------------------
# Dados (isolados para os testes poderem substituí-los)
# ---------------------------------------------------------------------------
def _catalog() -> List[Dict[str, Any]]:
    from backend.database import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM investment_products WHERE is_active = 1 ORDER BY rate_annual DESC, min_amount_minor ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def _balance(user_id: str, currency: str, amount: float) -> Dict[str, Any]:
    try:
        from backend.ai.tools.actions import _balance_info
        return _balance_info(user_id, currency, amount)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Deteção do que o cliente quer
# ---------------------------------------------------------------------------
_OPEN_CMD = re.compile(
    r"^\W*(?:(?:por favor|pf|pode(?:s|mos)?|agora|ja|entao|vamos|quero(?: que)?|queria(?: que)?|"
    r"preciso(?: que)?|gostava(?: que)?|va|vai)\W+)*(?:abr\w*|mostr\w*|leva\w*|passa\w*|ir|vai)\b")
_FORM_WORD = re.compile(r"\bformulario\b|\bform\b|\bsubscri\w*")
_PAGE_WORD = re.compile(r"\b(?:pagina|painel|ecra|separador|seccao|area)\b")
_OTHER_PAGE = re.compile(r"\b(?:despesas?|poupanc\w*|cartoes|cartao|extrato|contas?|operacoes|pagamentos|inicio|home|metas?)\b")
_INVEST_WORD = re.compile(r"\b(?:invest\w+|invist\w+|aplicar|aplica|aplico|subscrev\w+|subscricao|depositos?\s+a\s+prazo)\b")
_REQUEST_CUE = re.compile(
    r"\b(?:quero|queria|gostaria|gostava|desejo|preciso|pretendo|vou|vamos|decidi|fazer|faz|abrir|abre|abra|"
    r"criar|cria|bora|inicia\w*|comecar|ajuda(?:-?me)?)\b")
_NOT_A_REQUEST = re.compile(
    r"recomend|sugest|sugere|aconselh|melhor|simul|rentabil|quanto vou|diferenca|vantagens?|desvantagens?|riscos?|"
    r"o que e|como funciona|"
    # «o meu filho» não é consulta: só «os meus investimentos / a minha carteira / o meu depósito…» é
    r"\b(?:meus?|minhas?)\s+(?:investiment\w*|aplicac\w*|carteira|portfolio|depositos?)\b|"
    r"\b(?:carteira|resgat\w*|levant\w*|retir\w*|vender|ver|mostr\w*|consult\w*)\b")
_CANCEL = re.compile(r"\bcancela\w*|\besquece\w*|\bdesisto\b|\bdeixa (?:estar|para la|isso)\b|nao quero (?:mais )?(?:investir|nada)")
_SKIP_NAME = re.compile(
    r"\bsem nome\b|^\W*(?:nao|nenhum|nada|pula\w*|salta\w*|avanca|tanto faz|qualquer(?: um| nome)?|em branco)\W*$|"
    r"deixa em branco|nao (?:quero|preciso)(?: de)?(?: dar)?(?: um)? nome")
_NAME_IN_TEXT = re.compile(r"(?:chamad[oa]|com o nome|de nome|nome)\s*[:=]?\s*[\"“«']?([^\"”»'\n.,;]{2,60})", re.I)


def _wants_page(n: str, has_state: bool) -> bool:
    if not _OPEN_CMD.search(n) or _FORM_WORD.search(n):
        return False
    if "investiment" in n:
        return True
    return has_state and bool(_PAGE_WORD.search(n)) and not _OTHER_PAGE.search(n)


def _wants_form_now(n: str, has_state: bool) -> bool:
    if not _OPEN_CMD.search(n):
        return False
    if has_state:
        return not _wants_page(n, True) and not _OTHER_PAGE.search(n)
    return bool(_FORM_WORD.search(n)) and "investiment" in n


def _is_request(n: str) -> bool:
    if not _INVEST_WORD.search(n) or n.rstrip().endswith("?") or _NOT_A_REQUEST.search(n):
        return False
    return bool(_REQUEST_CUE.search(n) or re.match(r"^\W*(?:invest\w*|invist\w*|aplic\w*|subscrev\w*)\b", n))


_AMOUNT_WITH_UNIT = re.compile(r"(\d[\d. ]*\d|\d)\s*(?:mil\b|k\b|kz\b|kwanzas?\b|aoa\b)")


def _ambiguous_amount(n: str) -> bool:
    """Mais do que um valor diferente na mesma frase (ex.: «1000 kwanzas… de 100000 kwanzas»): não adivinhar."""
    vals = {re.sub(r"[. ]", "", m.group(1)) for m in _AMOUNT_WITH_UNIT.finditer(n)}
    return len(vals) > 1


def _looks_question(n: str, text: str) -> bool:
    return text.rstrip().endswith("?") or bool(QUESTION_START.search(n))


# ---------------------------------------------------------------------------
# Produtos: apresentação e correspondência
# ---------------------------------------------------------------------------
_STOP = {"de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "em", "o", "a", "os", "as", "um", "uma", "e", "para",
         "com", "por", "ao", "aos", "que", "se", "meu", "minha", "vou", "quero", "queria", "gostaria", "investir",
         "investimento", "investimentos", "aplicar", "subscrever", "fazer", "kz", "kwanzas", "kwanza", "aoa", "mil",
         "milhoes", "milhao", "valor", "montante", "pelo", "pela", "esse", "este", "isso", "ok", "sim", "entao"}
_CAT_WORDS = {"deposito_prazo": "deposito depositos prazo", "obrigacoes": "obrigacao obrigacoes titulos tesouro",
              "etf": "etf etfs", "fundos": "fundo fundos"}
_CUR_WORDS = {"USD": {"usd", "dolares", "dolar", "dollar", "dollars"}, "EUR": {"eur", "euros", "euro"}}


def _tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", _norm(s)) if w not in _STOP and len(w) > 1 and not w.isdigit()}


def _match(text: str, pool: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Produtos que correspondem ao que o cliente disse (número da lista ou nome)."""
    n = _norm(text)
    m = re.fullmatch(r"\W*(?:o\s+|a\s+|n\s*[oº°.]?\s*|numero\s*|opcao\s*)?(\d{1,2})\W*", n)
    if m:
        i = int(m.group(1))
        return [pool[i - 1]] if 1 <= i <= len(pool) else []
    q = _tokens(n)
    scored = []
    for r in pool:
        name_t = _tokens(r["name"])
        other_t = _tokens(f"{r['institution']} {_CAT_WORDS.get(r['category'], '')}")
        base = 2 * len(q & name_t) + len(q & (other_t - name_t))
        scored.append((base, r))
    best = max((s for s, _ in scored), default=0)
    if best > 0:
        top = [r for s, r in scored if s == best]
        if len(top) > 1:  # moeda dita desempata
            cur = [r for r in top if q & _CUR_WORDS.get(r["currency"], set())]
            top = cur or top
        return top
    for cur_code, words in _CUR_WORDS.items():  # só disse a moeda («o de dólares»)
        if q & words:
            return [r for r in pool if r["currency"] == cur_code]
    return []


def _pct(v: float) -> str:
    return f"{float(v):g}".replace(".", ",") + "%"


def _product_line(i: int, r: Dict[str, Any]) -> str:
    term = f"{r['term_months']} meses" if r.get("term_months") else "sem prazo fixo"
    return f"{i}. **{r['name']}** · {_pct(r['rate_annual'])} a.a. · {term} · mín. {fmt_money(r['min_amount_minor'] / 100, r['currency'])}"


def _min(r: Dict[str, Any]) -> float:
    return round(r["min_amount_minor"] / 100.0, 2)


def _by_id(rows: List[Dict[str, Any]], pid: Optional[str]) -> Optional[Dict[str, Any]]:
    return next((r for r in rows if r["id"] == pid), None) if pid else None


def _confident_amount(text: str, today: date) -> Optional[float]:
    """Montante só quando é claro: tem unidade (mil, Kz, USD…) ou é ≥ 1.000 (evita ler «364» de «BT 364»)."""
    s = _parse_slots(text, today)
    amt = s.get("amount")
    if not amt:
        return None
    unit = re.search(r"\b(?:mil|k|milh\w+|kz|kwanzas?|aoa|usd|eur|dolares?|euros?)\b", _norm(text))
    return float(amt) if (amt >= 1000 or unit) else None


# ---------------------------------------------------------------------------
# O que o cliente já disse: taxa, montante e finalidade (para não perguntar de novo)
# ---------------------------------------------------------------------------
_RATE_RX = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:%|por cento)|(?<![\d.,])(\d{1,2}[.,]\d{1,2})(?![\d])")
_PURPOSE_RX = re.compile(
    r"\bpara\s+(?!investir\b|aplicar\b|subscrever\b|ver\b|saber\b|mim\b|isso\b|fazer\b|comecar\b)(.+)$", re.I)
_PURPOSE_CUT = re.compile(r"[,.;!?]|\s+(?:no|na|nos|nas|em|com|ao|ate|por|que|e|a)\s+(?=\S)", re.I)


def _mentioned_rate(text: str) -> Optional[float]:
    """Taxa dita pelo cliente («18,5», «18.5%», «a 17 por cento»), só se for plausível (0–40 %)."""
    for m in _RATE_RX.finditer(text):
        raw = (m.group(1) or m.group(2) or "").replace(",", ".")
        try:
            v = float(raw)
        except ValueError:
            continue
        if 0 < v <= 40:
            return v
    return None


def _same_rate(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) < 0.05


def _by_rate(pool: List[Dict[str, Any]], rate: Optional[float]) -> List[Dict[str, Any]]:
    return [r for r in pool if rate is not None and _same_rate(r["rate_annual"], rate)]


def _narrow(found: List[Dict[str, Any]], amount: Optional[float], rate: Optional[float]) -> List[Dict[str, Any]]:
    """Com o que o cliente disse (taxa, montante) fica só o que serve; nunca devolve vazio."""
    pool = found
    if rate is not None:
        pool = _by_rate(pool, rate) or pool
    if amount:
        pool = [r for r in pool if _min(r) <= float(amount)] or pool
    return pool


def _purpose_name(text: str) -> Optional[str]:
    """«… para o meu filho» → «Para o meu filho» (fica como nome/nota do investimento)."""
    m = _PURPOSE_RX.search(text)
    if not m:
        return None
    s = _PURPOSE_CUT.split(m.group(1).strip(), 1)[0].strip(" \"“”«»'")
    if len(s) < 3 or len(s) > 60 or not re.search(r"[A-Za-zÀ-ÿ]{3}", s) or re.fullmatch(r"[\d\s.,]+(?:mil|kz)?", s, re.I):
        return None
    return "Para " + s


def _rate_note(prod: Dict[str, Any], rows: List[Dict[str, Any]], asked: Optional[float]) -> str:
    """Avisa quando a taxa dita não é a do produto escolhido (nunca fingir que bate certo)."""
    if asked is None or _same_rate(prod["rate_annual"], asked):
        return ""
    other = _by_rate(rows, asked)
    tail = f" Os {_pct(asked)} são de **{other[0]['name']}**." if other else ""
    return f"⚠️ Disse {_pct(asked)}, mas **{prod['name']}** rende **{_pct(prod['rate_annual'])}** a.a.{tail}"


# ---------------------------------------------------------------------------
# Ação e respostas
# ---------------------------------------------------------------------------
def _action(r: Dict[str, Any], amount: Optional[float], notes: str, partial: bool = False) -> Dict[str, Any]:
    months = r.get("term_months")
    est = None
    if amount:
        gross = amount * (r["rate_annual"] / 100.0) * ((months or 12) / 12.0)
        est = round(gross * 0.9 if r["category"] in _NET_TAX_CATS else gross, 2)
    return {
        "type": KIND, "product_id": r["id"], "product_name": r["name"], "institution": r["institution"],
        "category": r["category"], "currency": r["currency"], "rate_annual": r["rate_annual"],
        "term_months": months, "term_label": f"{months} meses" if months else "Sem prazo fixo",
        "min_amount": _min(r), "amount": amount or None, "est_return": est,
        "est_return_is_annual": not months, "notes": (notes or "")[:120], "partial": partial,
    }


def _state(slots: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": KIND, "slots": slots}


def _ask_product(pool: List[Dict[str, Any]], slots: Dict[str, Any], intro: str = "", hint: bool = False) -> Dict[str, Any]:
    slots["ask"] = "product"
    slots["candidates"] = [r["id"] for r in pool] if len(pool) < 9 else slots.get("candidates")
    if not slots["candidates"]:
        slots.pop("candidates", None)
    lines = [f"{intro}Em que investimento quer aplicar? Diga o número ou o nome:", ""]
    lines += [_product_line(i, r) for i, r in enumerate(pool, 1)]
    if hint:
        lines += ["", "Se preferir, diga «abrir o formulário» e eu abro já com o que tiver."]
    return {"reply": "\n".join(lines), "action": None, "pending": _state(slots)}


def _advance(user_id: str, slots: Dict[str, Any], rows: List[Dict[str, Any]], note: str = "", first: bool = False) -> Dict[str, Any]:
    prod = _by_id(rows, slots.get("product_id"))
    if not prod:
        pool = [r for r in rows if r["id"] in (slots.get("candidates") or [])] or rows
        return _ask_product(pool, slots, intro=note, hint=first)
    slots.pop("candidates", None)

    amount = slots.get("amount")
    if amount and amount < _min(prod):
        slots.pop("amount")
        note = f"O mínimo de **{prod['name']}** é **{fmt_money(_min(prod), prod['currency'])}**. "
        amount = None
    if not amount:
        slots["ask"] = "amount"
        return {"reply": f"{note}Quanto quer investir em **{prod['name']}**? (mínimo {fmt_money(_min(prod), prod['currency'])})",
                "action": None, "pending": _state(slots)}

    # O nome é opcional (fica na nota do formulário): com produto e montante já não se pergunta mais nada.
    action = _action(prod, float(amount), slots.get("name") or "")
    lines = ["Pronto! Abri o formulário de subscrição com tudo preenchido:",
             f"• Produto: **{prod['name']}**",
             f"• Montante: **{fmt_money(float(amount), prod['currency'])}**"]
    if slots.get("name"):
        lines.append(f"• Nome: {slots['name']}")
    warn = _rate_note(prod, rows, slots.get("rate_asked"))
    if warn:
        lines.append(f"\n{warn}")
    bal = _balance(user_id, prod["currency"], float(amount))
    if bal.get("has_account") is False:
        lines.append(f"\n⚠️ Não tem conta em {prod['currency']}: precisa de uma para debitar este investimento.")
    elif bal.get("has_sufficient_funds") is False:
        lines.append(f"\n⚠️ O saldo da conta em {prod['currency']} não chega para este montante.")
    lines.append("\nReveja e toque em **Confirmar** no formulário. Ainda **não foi investido**.")
    return {"reply": "\n".join(lines), "action": action, "pending": None}


def _open_form(slots: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    prod = _by_id(rows, slots.get("product_id"))
    if not prod:
        return {"reply": "Ainda não escolheu o produto, por isso abri a página de **Investimentos** no catálogo para o escolher.",
                "action": {"type": KIND, "product_id": None, "partial": True}, "pending": None}
    amount = slots.get("amount")
    if amount and amount < _min(prod):
        amount = None
    notes = slots.get("name") or ""
    lines = ["Abri o formulário de subscrição com o que já tinha:", f"• Produto: **{prod['name']}**"]
    missing = []
    if amount:
        lines.append(f"• Montante: **{fmt_money(float(amount), prod['currency'])}**")
    else:
        missing.append("o montante")
    if notes:
        lines.append(f"• Nome: {notes}")
    else:
        missing.append("o nome")
    warn = _rate_note(prod, rows, slots.get("rate_asked"))
    if warn:
        lines.append(f"\n{warn}")
    if missing:
        lines.append(f"\nFalta {' e '.join(missing)}: pode completar no formulário.")
    lines.append("Ainda **não foi investido**: reveja e toque em **Confirmar**.")
    return {"reply": "\n".join(lines), "action": _action(prod, float(amount) if amount else None, notes, partial=True), "pending": None}


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
def handle_investment_message(user_id: str, message: str, pending: Optional[Dict[str, Any]] = None,
                              today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """
    Devolve {"reply", "action", "pending"} ou None quando a mensagem não é do fluxo de investimento
    (as outras respostas do Copilot seguem normalmente).
    """
    today = today or date.today()
    text = (message or "").strip()
    if not text:
        return None
    n = _norm(text)
    state = pending if isinstance(pending, dict) and pending.get("type") == KIND else None
    has_state = state is not None

    if not has_state and not (_wants_page(n, False) or _wants_form_now(n, False) or _is_request(n)):
        return None

    rows = _catalog()
    slots: Dict[str, Any] = dict(state.get("slots") or {}) if has_state else {}
    ask = slots.get("ask")

    # 1) só a página
    if _wants_page(n, has_state):
        extra = " Deixei o pedido de investimento de lado; diga «quero investir» para o retomar." if has_state else ""
        return {"reply": "Abri a página de **Investimentos**." + extra, "pending": None,
                "action": {"type": "OPEN_INVESTMENTS", "title": "Painel de Investimentos", "category": "investments"}}

    def absorb_from_message():
        pool = [r for r in rows if r["id"] in (slots.get("candidates") or [])] or rows
        amt = _confident_amount(text, today)
        if amt and "amount" not in slots and not _ambiguous_amount(n):
            slots["amount"] = amt
        rate = _mentioned_rate(text)
        if rate is not None:
            slots["rate_asked"] = rate
        found = _match(text, pool)
        if not found and rate is not None:          # só disse a taxa («a 18,5%»)
            found = _by_rate(pool, rate)
        if len(found) > 1:
            found = _narrow(found, slots.get("amount"), rate)
        if len(found) == 1:
            slots["product_id"] = found[0]["id"]
        elif len(found) > 1 and "product_id" not in slots:
            slots["candidates"] = [r["id"] for r in found]
        m = _NAME_IN_TEXT.search(text)
        if m and "name" not in slots:
            slots["name"] = m.group(1).strip(" \"“”«»'")
        elif "name" not in slots:
            purpose = _purpose_name(text)
            if purpose:
                slots["name"] = purpose

    # 2) abrir já o formulário (com o que houver)
    if _wants_form_now(n, has_state):
        if not has_state:
            absorb_from_message()
        return _open_form(slots, rows)

    # 3) pedido novo
    if not has_state:
        absorb_from_message()
        return _advance(user_id, slots, rows, first=True)

    # 4) a meio das perguntas
    if ask == "name" and _SKIP_NAME.search(n):
        slots["name"] = ""
        return _advance(user_id, slots, rows)
    if _CANCEL.search(n):
        return {"reply": "Sem problema, cancelei o investimento. Em que mais posso ajudar?", "action": None, "pending": None}

    if ask == "product":
        pool = [r for r in rows if r["id"] in (slots.get("candidates") or [])] or rows
        found = _match(text, pool)
        rate = _mentioned_rate(text)
        if rate is not None:
            slots["rate_asked"] = rate
            if not found:
                found = _by_rate(pool, rate)
        if len(found) > 1:
            found = _narrow(found, slots.get("amount") or _confident_amount(text, today), rate)
        if not found:
            if _looks_question(n, text):
                return None
            amt = _confident_amount(text, today)
            if amt:
                slots["amount"] = amt
            return _ask_product(pool, slots, intro="Não encontrei esse produto. ")
        if len(found) > 1:
            slots["candidates"] = [r["id"] for r in found]
            return _ask_product(found, slots, intro="Há mais do que um com esse nome. ")
        slots["product_id"] = found[0]["id"]
        if not re.fullmatch(r"\W*(?:o\s+|a\s+|n\s*[oº°.]?\s*|numero\s*|opcao\s*)?\d{1,2}\W*", n):
            amt = _confident_amount(text, today)
            if amt and "amount" not in slots:
                slots["amount"] = amt
        return _advance(user_id, slots, rows)

    if ask == "amount":
        prod = _by_id(rows, slots.get("product_id"))
        parsed = _parse_slots(text, today)
        amt = parsed.get("amount")
        if not amt:
            if _looks_question(n, text):
                return None
            return {"reply": "Não percebi o montante. Diga, por exemplo, «500 mil» ou «250.000 Kz».",
                    "action": None, "pending": _state(slots)}
        cur = parsed.get("currency")
        if prod and cur and cur != prod["currency"]:
            return {"reply": f"Este produto é em **{prod['currency']}**: indique o montante nessa moeda.",
                    "action": None, "pending": _state(slots)}
        slots["amount"] = float(amt)
        return _advance(user_id, slots, rows)

    if ask == "name":
        if _looks_question(n, text):
            return None
        slots["name"] = re.sub(r"\s+", " ", text).strip(" \"“”«»'")[:80]
        return _advance(user_id, slots, rows)

    return None
