"""
Ferramentas de AÇÃO do Copilot: preparam metas, despesas, transferências e depósitos.

Regra de ouro: estas ferramentas NUNCA movimentam dinheiro nem gravam nada.
Cada uma valida os dados e devolve uma `action` que o frontend usa para pré-preencher
o formulário certo — quem carrega em «Confirmar / Criar / Registar» é sempre o utilizador.

Reutilizam os construtores de `intents.py` (cálculo de prazos, taxas, validação de IBAN),
por isso o resultado é idêntico ao do fluxo guiado clássico.
"""
import re
from datetime import date
from typing import Any, Dict, List, Optional

from backend.ai.intents import (
    CATEGORIAS,
    _build_deposit,
    _build_expense,
    _build_goal,
    _build_transfer_iban,
    _build_transfer_internal,
    find_iban,
    iban_ok,
)
from backend.services.ledger import get_user_accounts

GOAL_ICONS = ("target", "home", "car", "travel", "laptop", "education", "award", "shield")
CURRENCIES = ("AOA", "EUR", "USD")

_EMAIL_RE = re.compile(r"^[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+$")
_YM_RE = re.compile(r"^(\d{4})-(\d{1,2})$")


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------
def _fail(message: str, **extra: Any) -> Dict[str, Any]:
    """Erro explicado ao modelo (que o transforma numa pergunta curta ou num aviso ao cliente)."""
    return {"ok": False, "executed": False, "error": message, **extra}


def _ok(action: Dict[str, Any], summary: str, **extra: Any) -> Dict[str, Any]:
    return {
        "ok": True,
        "executed": False,  # nada foi feito — o cliente ainda tem de confirmar no formulário
        "requires_user_confirmation": True,
        "action": action,
        "summary": summary,
        **extra,
    }


def _amount(value: Any) -> Optional[float]:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _ym(value: Any) -> Optional[List[int]]:
    """'2027-08' → [2027, 8]."""
    if not value:
        return None
    m = _YM_RE.match(str(value).strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    return [year, month] if 1 <= month <= 12 and 2000 <= year <= 2100 else None


def _currency(value: Any) -> str:
    cur = str(value or "AOA").strip().upper()
    return cur if cur in CURRENCIES else "AOA"


# ---------------------------------------------------------------------------
# Meta de poupança
# ---------------------------------------------------------------------------
_GOAL_FIELDS = {
    "kind": "o tipo de meta (nome)",
    "target": "o valor total da meta",
    "months": "o prazo (em meses ou mês/ano final)",
    "start": "o mês em que começa",
    "day": "o dia do mês do débito automático",
}


def tool_prepare_savings_goal(
    user_id: str,
    name: Optional[str] = None,
    icon_key: Optional[str] = None,
    target_amount: Optional[float] = None,
    months: Optional[int] = None,
    deadline: Optional[str] = None,
    monthly_amount: Optional[float] = None,
    initial_saved: Optional[float] = None,
    auto_debit: Optional[bool] = None,
    start_month: Optional[str] = None,
    debit_day: Optional[int] = None,
) -> Dict[str, Any]:
    """Prepara uma META DE POUPANÇA (não uma despesa) para o cliente rever e criar."""
    name = (name or "").strip()
    if not name:
        name = "Poupança"

    target = _amount(target_amount)
    if not target:
        return _fail("Falta o valor total da meta em Kz.", missing=["target_amount"])

    saved = _amount(initial_saved) or 0.0
    if saved >= target:
        return _fail("O saldo inicial não pode ser igual ou superior ao valor da meta.")

    icon = icon_key if icon_key in GOAL_ICONS else "target"
    deadline_ym = _ym(deadline)
    if deadline and not deadline_ym:
        return _fail("O prazo final tem de vir no formato AAAA-MM (ex.: 2027-08).")
    months_n = int(months) if months and int(months) > 0 else None
    monthly = _amount(monthly_amount) or 0.0

    if not (months_n or deadline_ym or monthly):
        return _fail("Falta o prazo: em quantos meses, até que mês/ano, ou quanto guarda por mês.",
                     missing=["months|deadline|monthly_amount"])

    auto = True if auto_debit is None else bool(auto_debit)
    slots: Dict[str, Any] = {"name": name[:60], "icon_key": icon, "target": target, "auto": auto}
    if saved:
        slots["saved"] = saved
    if months_n:
        slots["months"] = months_n
    if deadline_ym:
        slots["deadline"] = deadline_ym
    if monthly:
        slots["monthly"] = monthly

    if auto:
        day = int(debit_day) if debit_day else None
        if day is not None and not 1 <= day <= 31:
            return _fail("O dia do débito tem de estar entre 1 e 31.")
        if not day:
            return _fail("Falta o dia do mês para o débito automático (ou o cliente prefere sem débito automático).",
                         missing=["debit_day"])
        slots["day"] = day
        start = _ym(start_month)
        if start_month and not start:
            return _fail("O mês de início tem de vir no formato AAAA-MM.")
        if not start:  # sem mês dito: começa já este mês (o construtor salta para o seguinte se o dia já passou)
            today = date.today()
            start = [today.year, today.month]
        slots["start"] = start

    built = _build_goal(slots, date.today())
    action = built.get("action")
    if not action:
        pending = (built.get("pending") or {}).get("slots") or {}
        step = pending.get("ask")
        return _fail(f"Ainda falta {_GOAL_FIELDS.get(step, 'um dado')} para montar a meta.", missing=[step or "dados"])
    return _ok(action, built.get("reply") or "Meta preparada.")


# ---------------------------------------------------------------------------
# Despesa
# ---------------------------------------------------------------------------
def tool_prepare_expense(
    user_id: str,
    name: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    expense_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepara o REGISTO de uma despesa já feita (gasto passado), para o cliente rever e registar."""
    value = _amount(amount)
    if not value:
        return _fail("Falta o valor da despesa em Kz.", missing=["amount"])
    cat = category if category in CATEGORIAS else "Outros"
    slots: Dict[str, Any] = {"amount": value, "category": cat, "name": (name or "").strip()[:120] or f"Despesa em {cat}"}
    if expense_date:
        try:
            parsed = date.fromisoformat(str(expense_date)[:10])
        except ValueError:
            return _fail("A data da despesa tem de vir no formato AAAA-MM-DD.")
        if parsed > date.today():
            return _fail("A data da despesa não pode ser no futuro.")
        slots["date"] = parsed.isoformat()
    built = _build_expense(slots, date.today())
    return _ok(built["action"], built["reply"])


# ---------------------------------------------------------------------------
# Transferência (por conta BankAO / e-mail OU por IBAN — nunca misturados)
# ---------------------------------------------------------------------------
def _balance_info(user_id: str, currency: str, amount: float) -> Dict[str, Any]:
    acc = next((a for a in get_user_accounts(user_id) if a["currency"] == currency), None)
    if not acc:
        return {"has_account": False}
    bal = float(acc["balance_decimal"])
    return {"has_account": True, "available_balance": bal, "has_sufficient_funds": bal >= amount}


def tool_prepare_transfer(
    user_id: str,
    method: str,
    destination: str,
    amount: float,
    currency: str = "AOA",
    beneficiary_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prepara uma TRANSFERÊNCIA. `method`:
      • 'account' → conta BankAO (número de conta ou e-mail do cliente) → formulário «entre contas»
      • 'iban'    → IBAN de outro banco → formulário «por IBAN»
    O destino tem de corresponder ao método: um IBAN nunca vai para o campo da conta e vice-versa.
    """
    method = (method or "").strip().lower()
    dest = (destination or "").strip()
    value = _amount(amount)
    cur = _currency(currency)
    if not value:
        return _fail("Falta o valor da transferência.", missing=["amount"])
    if not dest:
        return _fail("Falta o destinatário (nº de conta BankAO, e-mail ou IBAN).", missing=["destination"])

    iban_hit = find_iban(dest)
    looks_iban = bool(iban_hit and iban_hit[0] == re.sub(r"\s+", "", dest).upper())

    if method not in ("account", "iban"):
        method = "iban" if looks_iban else "account"

    name = (beneficiary_name or "").strip()[:80]

    if method == "iban":
        if not looks_iban:
            return _fail("O destino indicado não é um IBAN. Peça ao cliente o IBAN completo "
                         "ou use method='account' se for um número de conta BankAO.")
        iban = iban_hit[0]
        built = _build_transfer_iban({"to_iban": iban, "amount": value, "currency": cur, "beneficiary_name": name})
        extra = {"iban_valid": iban_ok(iban)}
    else:
        if looks_iban:
            return _fail("O destino indicado é um IBAN. Use method='iban' (a transferência por IBAN tem outro formulário).")
        slots: Dict[str, Any] = {"amount": value, "currency": cur, "beneficiary_name": name}
        if _EMAIL_RE.match(dest):
            slots["to_email"] = dest
        else:
            digits = re.sub(r"\D", "", dest)
            if not 8 <= len(digits) <= 14:
                return _fail("O número de conta BankAO deve ter entre 8 e 14 dígitos (ex.: 0040 1234 5678) — "
                             "confirme o número com o cliente.")
            slots["to_account_number"] = digits
        built = _build_transfer_internal(slots)
        extra = {}

    action = built.get("action")
    if not action:
        return _fail(built.get("reply") or "Faltam dados para preparar a transferência.")
    return _ok(action, built["reply"], **_balance_info(user_id, cur, value), **extra)


# ---------------------------------------------------------------------------
# Depósito Express (Multicaixa Express)
# ---------------------------------------------------------------------------
def tool_prepare_deposit(user_id: str, phone_number: str, amount: float) -> Dict[str, Any]:
    digits = re.sub(r"\D", "", phone_number or "")
    if digits.startswith("244") and len(digits) == 12:
        digits = digits[3:]
    if not (len(digits) == 9 and digits.startswith("9")):
        return _fail("O telemóvel do Multicaixa Express deve ter 9 dígitos e começar por 9.", missing=["phone_number"])
    value = _amount(amount)
    if not value:
        return _fail("Falta o valor do depósito em Kz.", missing=["amount"])
    built = _build_deposit({"phone_number": digits, "amount": value})
    return _ok(built["action"], built["reply"])


# ---------------------------------------------------------------------------
# Investimento (subscrição de um produto do catálogo)
# ---------------------------------------------------------------------------
def _norm_txt(value: Any) -> str:
    import unicodedata
    txt = unicodedata.normalize("NFD", str(value or "").lower())
    return re.sub(r"[^a-z0-9% ]+", " ", "".join(c for c in txt if unicodedata.category(c) != "Mn")).strip()


def _kz(v: float) -> str:
    """500000 → 500.000,00 (formato angolano)."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _find_product(rows: List[Any], query: str) -> Any:
    """Devolve o produto (ou lista de candidatos se ambíguo / None se não existir)."""
    q = _norm_txt(query)
    for r in rows:
        if r["id"] == query:
            return r
    words = [w for w in q.split() if len(w) > 1]
    hits = [r for r in rows if q and q in _norm_txt(f"{r['name']} {r['institution']}")]
    if not hits and words:
        hits = [r for r in rows if all(w in _norm_txt(f"{r['name']} {r['institution']} {r['category']}") for w in words)]
    if len(hits) == 1:
        return hits[0]
    return hits or None


def tool_prepare_investment(
    user_id: str,
    product: Optional[str] = None,
    amount: Optional[float] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepara a SUBSCRIÇÃO de um produto do catálogo para o cliente rever no formulário de investimentos."""
    from backend.database import get_connection

    if not (product or "").strip():
        return _fail("Falta o produto de investimento (ex.: um Depósito a Prazo do catálogo).", missing=["product"])
    value = _amount(amount)
    if not value:
        return _fail("Falta o montante a investir.", missing=["amount"])

    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM investment_products WHERE is_active = 1").fetchall()
    found = _find_product(rows, product.strip())
    if not found:
        return _fail("Não encontrei esse produto no catálogo. Consulte o catálogo e peça ao cliente para escolher um.",
                     missing=["product"])
    if isinstance(found, list):
        names = [f"{r['name']} ({r['institution']})" for r in found[:5]]
        return _fail("Há vários produtos possíveis; pergunte ao cliente qual quer: " + "; ".join(names), missing=["product"])

    p = found
    cur = p["currency"]
    min_amount = round(p["min_amount_minor"] / 100.0, 2)
    if value < min_amount:
        return _fail(f"O montante mínimo deste produto é {_kz(min_amount)} {cur}.", min_amount=min_amount)

    months = p["term_months"]
    gross = value * (p["rate_annual"] / 100.0) * ((months or 12) / 12.0)
    net = gross * 0.9 if p["category"] in ("deposito_prazo", "obrigacoes") else gross
    action = {
        "type": "INVESTMENT_APPLY",
        "product_id": p["id"],
        "product_name": p["name"],
        "institution": p["institution"],
        "category": p["category"],
        "currency": cur,
        "rate_annual": p["rate_annual"],
        "term_months": months,
        "term_label": f"{months} meses" if months else "Sem prazo fixo",
        "min_amount": min_amount,
        "amount": value,
        "est_return": round(net, 2),
        "est_return_is_annual": not months,
        "notes": (notes or "").strip()[:120],
    }
    summary = (f"Subscrição preparada: {_kz(value)} {cur} em {p['name']}. "
               "Ainda não foi feita: toque no botão para rever e confirmar no formulário.")
    return _ok(action, summary, **_balance_info(user_id, cur, value))
