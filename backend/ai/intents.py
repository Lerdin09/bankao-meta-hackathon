"""
Interpretação dos pedidos ao Copilot (poupança, despesa, transferência, depósito).

Princípios:
  • A IA prepara tudo, mas NUNCA conclui: cada ação devolvida só preenche um formulário;
    quem carrega em "Confirmar/Criar/Registar" é sempre o utilizador.
  • Nunca se inventa dados. Se falta algo essencial (valor, destino…), devolve-se uma
    pergunta (``ask``) e um ``pending`` que o frontend reenvia na mensagem seguinte.
  • O interpretador determinístico tem prioridade sobre o JSON do modelo, que só é aceite
    depois de validado.
"""
import json
import math
import re
import unicodedata
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend.ai.prompts import COUNTRY_MAP

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
IBAN_LEN = {"AO": 25, "PT": 25, "ES": 24, "FR": 27, "DE": 22, "IT": 27, "GB": 22,
            "BR": 29, "CV": 25, "MZ": 25, "US": 26}
EUR_COUNTRIES = {"PT", "ES", "FR", "DE", "IT"}
FEE_IBAN = 2.5       # % — igual ao frontend (bank-transfer.js)
FEE_INTERNAL = 1.0   # % — igual ao backend (/api/transfers/internal)

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
MESES_NOME = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
              "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
_MESES_RE = "|".join(MESES)

CATEGORIAS = ("Alimentação", "Transporte", "Habitação", "Telecomunicações", "Eletrónicos", "Lazer", "Saúde", "Poupança", "Outros")

# Palavras-chave (aplicadas ao texto normalizado: minúsculas e sem acentos)
SAVINGS_KW = re.compile(r"poupanc|poupar|juntar dinheiro|guardar dinheiro|economizar|cofrinho|"
                        r"\b(?:criar|nova|abrir|definir|fazer)\s+(?:uma\s+)?meta\b|"
                        r"\bmeta\b(?!\s+(?:de\s+)?(?:gasto|gastos|despesa|despesas|orcamento|categoria))")
TRANSFER_KW = re.compile(r"transfer|\benvi(?:a|ar|e|o)\b|\bmand(?:a|ar|e)\b")
DEPOSIT_KW = re.compile(r"deposit|multicaixa|express|\bcarreg")
EXPENSE_KW = re.compile(r"despesa|gastei|\bgasto\b|comprei|paguei|\bregist(?:a|ar|e|o)\b|\banota")
QUESTION_START = re.compile(r"^\s*(?:como|qual|quais|o que|que |quanto|quando|onde|porque|por que|posso|pode|sera|existe|e possivel)\b")


# ---------------------------------------------------------------------------
# Utilitários de texto
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    """Minúsculas sem acentos (mantém o comprimento do texto para reutilizar posições)."""
    out = []
    for ch in s:
        d = unicodedata.normalize("NFD", ch)
        out.append(d[0] if d else ch)
    return "".join(out).lower()


def _blank(text: str, spans: List[Tuple[int, int]]) -> str:
    chars = list(text)
    for a, b in spans:
        for i in range(a, min(b, len(chars))):
            chars[i] = " "
    return "".join(chars)


def fmt_money(value: float, currency: str = "AOA") -> str:
    sym = {"AOA": "Kz", "EUR": "€", "USD": "$"}.get(currency, currency)
    if abs(value - round(value)) < 0.005:
        txt = f"{int(round(value)):,}".replace(",", ".")
    else:
        txt = f"{value:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"{txt} {sym}"


# ---------------------------------------------------------------------------
# Extração de dados (IBAN, conta, e-mail, telefone, datas, valores)
# ---------------------------------------------------------------------------
_IBAN_START = re.compile(r"\b([A-Za-z]{2}\d{2})(?:[ ]?[0-9A-Za-z]){6,34}")


def find_iban(text: str) -> Optional[Tuple[str, int, int]]:
    """Devolve (iban_normalizado, início, fim). Aceita espaços entre os grupos."""
    for m in _IBAN_START.finditer(text):
        raw = m.group(0)
        tokens = re.split(r"\s+", raw)
        kept = [tokens[0]]
        for t in tokens[1:]:
            if re.fullmatch(r"[0-9A-Za-z]+", t) and re.search(r"\d", t):
                kept.append(t)
            else:
                break
        joined = "".join(kept).upper()
        country = joined[:2]
        if country in IBAN_LEN:
            if len(joined) < IBAN_LEN[country]:
                continue
            joined = joined[:IBAN_LEN[country]]
        elif len(joined) < 15:
            continue
        # fim = posição onde terminam os caracteres consumidos
        consumed, end = 0, m.start()
        for ch_i in range(m.start(), m.end()):
            if text[ch_i] != " ":
                consumed += 1
            end = ch_i + 1
            if consumed >= len(joined):
                break
        return joined, m.start(), end
    return None


def iban_ok(iban: str) -> bool:
    iban = iban.replace(" ", "").upper()
    if not iban.isalnum() or not (15 <= len(iban) <= 34):
        return False
    if iban[:2] in IBAN_LEN and len(iban) != IBAN_LEN[iban[:2]]:
        return False
    try:
        return int("".join(str(int(c, 36)) for c in iban[4:] + iban[:4])) % 97 == 1
    except ValueError:
        return False


_EMAIL = re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+")
_ACC_BANKAO = re.compile(r"(?<!\d)(0040[\s.-]?\d{4}[\s.-]?\d{4})(?!\d)")
_ACC_GENERIC = re.compile(r"\bconta\s*(?:n[ºo°.]*\s*|numero\s*|num\.?\s*)?:?\s*(\d[\d\s.-]{6,18}\d)", re.I)
_PHONE = re.compile(r"(?<![\d.])(9\d{2}[\s.-]?\d{3}[\s.-]?\d{3})(?!\d)")


def normalize_spoken_text(text: str) -> str:
    """
    Normaliza texto transcrito por reconhecimento de voz:
    - E-mails ditados: 'ana ponto ferreira arroba bankao ponto ao' -> 'ana.ferreira@bankao.ao'
    - 'joao arroba bankao ao' -> 'joao@bankao.ao'
    - 'ana ferreira arroba bankao' -> 'ana.ferreira@bankao.ao'
    """
    if not text:
        return text
    t = text

    # Normalizar palavras de e-mail faladas
    t = re.sub(r"\s*(?:arroba|\barrobas?\b|@)\s*", "@", t, flags=re.I)
    t = re.sub(r"(?<=\w)\s+(?:ponto|dot|\.)\s+(?=\w)", ".", t, flags=re.I)
    t = re.sub(r"\s*@\s*", "@", t)
    t = re.sub(r"\s*\.\s*", ".", t)

    # Nomes com espaço antes de @: "ana ferreira@..." -> "ana.ferreira@..."
    t = re.sub(r"([A-Za-z0-9_-]+)\s+([A-Za-z0-9_-]+)@", r"\1.\2@", t)

    # Domínio falado sem ponto final: "@bankao ao" -> "@bankao.ao"
    t = re.sub(r"@bankao(?:\s+ao|\.ao)?\b", "@bankao.ao", t, flags=re.I)
    t = re.sub(r"@bankao\b(?!\.)", "@bankao.ao", t, flags=re.I)
    t = re.sub(r"@gmail(?:\s+com|\.com)?\b", "@gmail.com", t, flags=re.I)

    return t


def find_account(text: str) -> Optional[Tuple[str, int, int]]:
    m = _ACC_BANKAO.search(text)
    if m:
        return re.sub(r"\D", "", m.group(1)), m.start(1), m.end(1)
    m = _ACC_GENERIC.search(text)
    if m:
        digits = re.sub(r"\D", "", m.group(1))
        if 8 <= len(digits) <= 14:
            return digits, m.start(1), m.end(1)
    return None


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def find_deadline(text_n: str, today: date) -> Tuple[Optional[Tuple[int, int]], List[Tuple[int, int]], str]:
    """Devolve ((ano, mês) | None, spans a mascarar, nota)."""
    m = re.search(rf"\b({_MESES_RE})\s*(?:de|do|,|-|/)?\s*(20\d{{2}})\b", text_n)
    if m:
        return (int(m.group(2)), MESES[m.group(1)]), [m.span()], ""
    m = re.search(r"(?<!\d)(0?[1-9]|1[0-2])\s*[/-]\s*(20\d{2})(?!\d)", text_n)
    if m:
        return (int(m.group(2)), int(m.group(1))), [m.span()], ""
    m = re.search(r"(?<!\d)(20\d{2})-(0[1-9]|1[0-2])(?!\d)", text_n)
    if m:
        return (int(m.group(1)), int(m.group(2))), [m.span()], ""
    m = re.search(r"\b(?:em|daqui a|dentro de|ate daqui a)\s+(\d{1,3})\s*(mes(?:es)?|anos?)\b", text_n)
    if m:
        n = int(m.group(1)) * (12 if m.group(2).startswith("ano") else 1)
        d = _add_months(today, n)
        return (d.year, d.month), [m.span()], ""
    m = re.search(rf"\b(?:em|ate|no mes de|para)\s+({_MESES_RE})\b", text_n)
    if m:
        mes = MESES[m.group(1)]
        ano = today.year if mes >= today.month else today.year + 1
        return (ano, mes), [m.span(1)], ""
    m = re.search(r"\b(?:em|ate|no ano de|ano de|ano)\s+(20\d{2})\b", text_n)
    if m:
        return (int(m.group(1)), 12), [m.span(1)], "Como indicou só o ano, assumi Dezembro."
    return None, [], ""



_START_PHRASE = re.compile(
    rf"\b(?:comec\w*|inici\w*|deposit\w*|poupar|a\s+partir)\b[^.;]{{0,45}}?"
    rf"(?P<date>(?:dia\s+)?(?:(?P<d>\d{{1,2}})\s+de\s+)?(?P<mes>{_MESES_RE})\b(?:\s+de\s+(?P<ano>20\d{{2}}))?)")


def find_start(n: str, today: date) -> Tuple[Optional[Dict[str, Any]], List[Tuple[int, int]]]:
    """«começar a depositar no dia 3 de janeiro» → ({y, m, day}, [span]). «até agosto» nunca é início."""
    for m in _START_PHRASE.finditer(n):
        if re.search(r"\bate\b", n[m.start():m.start("date")]):
            continue
        mes = MESES[m.group("mes")]
        y = int(m.group("ano")) if m.group("ano") else (today.year if mes >= today.month else today.year + 1)
        out: Dict[str, Any] = {"y": y, "m": mes}
        if m.group("d") and 1 <= int(m.group("d")) <= 31:
            out["day"] = int(m.group("d"))
        return out, [m.span("date")]
    return None, []

_NUM = r"(?:\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d+)?)"
_AMOUNT = re.compile(
    rf"(?<![\w.,])(?P<num>{_NUM})(?:\s*(?P<mult>milhoes|milhao|mil|k)\b)?"
    r"(?:\s*(?P<cur>kz|kzs|kwanzas?|aoa|akz|eur|euros?|usd|dolares?|€|\$)(?![a-z]))?")


def _to_float(num: str) -> float:
    s = num.strip()
    if re.fullmatch(r"\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?", s):
        s = s.replace(".", "").replace(" ", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    return float(s)


def find_amounts(text_n: str) -> List[Dict[str, Any]]:
    """Todos os valores monetários do texto, já multiplicados (50mil → 50000)."""
    found = []
    for m in _AMOUNT.finditer(text_n):
        try:
            value = _to_float(m.group("num"))
        except ValueError:
            continue
        mult = m.group("mult")
        if mult:
            value *= 1_000_000 if mult.startswith("milh") else 1_000
        cur = m.group("cur")
        currency = None
        if cur:
            currency = "EUR" if cur in ("eur", "euro", "euros", "€") else \
                       "USD" if cur in ("usd", "dolar", "dolares", "$") else "AOA"
        strong = bool(mult or cur)
        if value <= 0:
            continue
        found.append({"value": round(value, 2), "span": m.span(), "strong": strong, "currency": currency})
    return found


def _role(text_n: str, amt: Dict[str, Any]) -> str:
    a, b = amt["span"]
    before = text_n[max(0, a - 32):a]
    after = text_n[b:b + 18]
    if re.search(r"(?:ja\s+tenho|ja\s+poupei|ja\s+tenho\s+guardado|saldo\s+inicial|comecar?\s+com|comeco\s+com|inicial(?:mente)?(?:\s+de)?|entrada\s+de)\s*$", before):
        return "initial"
    if re.search(r"^\s*(?:por\s+m[e]s|/\s*mes|ao\s+mes|mensais|mensal|todos\s+os\s+meses|cada\s+mes)", after) or \
       re.search(r"(?:mensal(?:mente)?|por\s+mes|todos\s+os\s+meses)\s*(?:de|:)?\s*$", before):
        return "monthly"
    return "main"


def _pick_main(amounts: List[Dict[str, Any]], min_bare: float = 1.0) -> Optional[Dict[str, Any]]:
    strong = [a for a in amounts if a["strong"]]
    if strong:
        return strong[0]
    bare = [a for a in amounts if a["value"] >= min_bare]
    return bare[0] if bare else None


# ---------------------------------------------------------------------------
# Nome do beneficiário / da despesa / da meta
# ---------------------------------------------------------------------------
_NAME_STOP = {"iban", "conta", "com", "de", "do", "da", "dos", "das", "no", "na", "valor", "kz", "kwanzas", "kwanza",
              "para", "e", "o", "a", "que", "por", "via", "email", "e-mail", "nome", "montante", "quantia",
              "numero", "aoa", "euros", "euro", "dolares", "bankao", "bank", "transferencia", "transferir"}


def _clean_name_words(raw: str) -> str:
    words = []
    for w in re.split(r"\s+", raw.strip()):
        wn = _norm(w).strip(".,;:")
        if not w or wn in _NAME_STOP or re.search(r"\d|@", w):
            if words:
                break
            if wn in _NAME_STOP:
                continue
            break
        words.append(w.strip(".,;:"))
        if len(words) >= 5:
            break
    return " ".join(words).strip()


def find_beneficiary(text: str) -> str:
    m = re.search(r"(?:nome(?:\s+do\s+benefici[aá]rio)?|benefici[aá]rio|titular)\s*(?:[:=]|[eé]\b)?\s*:?\s*([A-Za-zÀ-ÿ][^\n,;]*)", text, re.I)
    if m:
        name = _clean_name_words(m.group(1))
        if name:
            return name.title() if name.islower() else name
    m = re.search(r"\bpara\s+(?:o\s+|a\s+)?([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\s]*)(?![A-Za-zÀ-ÿ@.\w])", text, re.I)
    if m and text[m.end():m.end() + 1] not in ("@", ".") :
        name = _clean_name_words(m.group(1))
        if name and _norm(name) not in _NAME_STOP:
            return name.title() if name.islower() else name
    return ""



_CAT_SAID = {   # só o nome da própria categoria: «supermercado», «casa» ou «poupança de carro» são descrição, não categoria
    "Alimentação": r"alimentacao", "Transporte": r"transportes?", "Habitação": r"habitacao",
    "Telecomunicações": r"telecomunicacoes|telecom", "Eletrónicos": r"eletronicos?|electronicos?",
    "Lazer": r"lazer", "Saúde": r"saude", "Outros": r"outros",
}
_CAT_PHRASE = re.compile(
    r"\b(?:(?:em|na|no|de|como|para|categoria)\s+)+(?:categoria\s+)?(?:eletr[oó]nicos?|electr[oó]nicos?|"
    r"alimenta[cç][aã]o|transportes?|habita[cç][aã]o|telecomunica[cç][oõ]es|telecom|lazer|sa[uú]de|outros)\b",
    re.I)


def explicit_category(n: str) -> Optional[str]:
    """Categoria que o cliente nomeou («em eletrónicos», «categoria saúde»); None se não disse nenhuma."""
    for cat, words in _CAT_SAID.items():
        if re.search(r"\b(?:em|na|no|de|como|para|categoria)\s+(?:categoria\s+)?(?:" + words + r")\b", n):
            return cat
    return None


def detect_category(text_n: str) -> str:
    rules = [
        ("Poupança", r"poupanc|poupar|cofrinho|aforro|deposito a prazo|fundo de emerg|reserva"),
        ("Investimento", r"invest|bodiva|acoes|titulos|fundo de invest"),
        ("Alimentação", r"supermercado|\bmercado\b|comida|almoco|jantar|lanche|restaurante|\bkero\b|\bmaxi\b|candando|alimenta|\bpao\b|refeicao|padaria"),
        ("Transporte", r"\btaxi\b|yango|\buber\b|combustivel|gasolina|gasoleo|sonangol|transporte|\bcarro\b|viagem|portagem|oficina"),
        ("Habitação", r"\brenda\b|\bcasa\b|energia|\bluz\b|\bende\b|\bagua\b|\bepal\b|condominio|habita"),
        ("Telecomunicações", r"unitel|\bzap\b|dstv|internet|\bnet\b|\bsaldo\b|recarga|telecom|africell|movicel|"
                             r"(?:conta|fatura|mensalidade|plano)\s+d[oa]\s+(?:telefone|telemovel|celular)"),
        ("Eletrónicos", r"eletronic|electronic|telefone|telemovel|celular|smartphone|iphone|samsung|xiaomi|tecno\b|tablet|ipad|"
                        r"computador|portatil|laptop|\btv\b|televis|auscultador|\bfones?\b|headphone|airpod|consola|playstation|"
                        r"\bps[45]\b|xbox|camara|carregador|powerbank|monitor|impressora|\bgadget"),
        ("Lazer", r"praia|festa|cinema|\bbar\b|lazer|balada|\bshow\b|passeio|jogo"),
        ("Saúde", r"farmacia|remedio|hospital|clinica|saude|medico|consulta"),
    ]
    for cat, rx in rules:
        if re.search(rx, text_n):
            return cat
    return "Outros"


def _goal_icon_and_name(text: str, text_n: str) -> Tuple[str, str]:
    table = [
        (r"carro|automovel|viatura|\bmota\b|moto\b", "car", "Carro"),
        (r"\bcasa\b|apartamento|moradia|terreno|habitacao|imovel", "home", "Casa"),
        (r"viagem|ferias|passagem|bilhete|turismo", "travel", "Viagem"),
        (r"telemovel|celular|computador|laptop|portatil|iphone|tablet|\btv\b|televisao", "laptop", "Tecnologia"),
        (r"faculdade|curso|estudos?|propina|escola|mestrado|universidade", "education", "Estudos"),
        (r"casamento|noivado|lobolo|festa de", "award", "Casamento"),
        (r"emergencia|reserva|imprevisto|seguranca", "shield", "Reserva de emergência"),
    ]
    for rx, icon, label in table:
        if re.search(rx, text_n):
            return icon, label
    m = re.search(r"(?:poupan[cç]a|meta|objetivo)\s+(?:para|de|do|da|pra)\s+(?:(?:comprar|ter|fazer|pagar)\s+)?(?:um|uma|o|a)?\s*"
                  r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{1,40}?)(?=\s+(?:que|em|ate|até|com|de\s+\d|no|na)\b|[,.\d]|$)", text, re.I)
    if m:
        nm = m.group(1).strip()
        if nm and _norm(nm) not in _NAME_STOP:
            return "target", nm[:1].upper() + nm[1:]
    return "target", "Nova meta"


# ---------------------------------------------------------------------------
# Cálculos
# ---------------------------------------------------------------------------
def _months_between(today: date, y: int, m: int) -> int:
    return (y - today.year) * 12 + (m - today.month)


def _fees(amount: float, pct: float) -> Tuple[float, float]:
    fee = round(amount * pct / 100, 2)
    return fee, round(amount - fee, 2)


# ---------------------------------------------------------------------------
# Construtores de ação (cada um devolve (ação|None, pergunta|None, pending|None, resposta|None))
# ---------------------------------------------------------------------------
def _ask(kind: str, slots: Dict[str, Any], question: str) -> Dict[str, Any]:
    return {"action": None, "reply": question, "pending": {"type": kind, "slots": slots}}


def _done(action: Dict[str, Any], reply: str) -> Dict[str, Any]:
    return {"action": action, "reply": reply, "pending": None}


_GOAL_CTX = {"home": "a casa", "car": "o carro", "travel": "a viagem", "laptop": "o equipamento",
             "education": "o curso", "award": "o evento"}
_NUM_WORDS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
              "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12}
_START_STOP = re.compile(r"sem debito|sem automatic|debito manual|\bmanual\b|nao quero (?:o )?(?:debito )?automatic")


def _clamp_day(y: int, m: int, d: int) -> date:
    last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
    return date(y, m, min(d, last))


def _fmt_date(d: date) -> str:
    return f"{d.day} de {MESES_NOME[d.month].lower()} de {d.year}"


def _parse_months(n: str) -> Optional[int]:
    """Duração em meses: «15 meses», «2 anos», «1 ano e meio», «um ano», «meio ano»."""
    if re.search(r"\bmeio ano\b", n):
        return 6
    m = re.search(r"(\d{1,3}|" + "|".join(_NUM_WORDS) + r")\s*(anos?|mes(?:es)?)\b(\s+e\s+meio)?", n)
    if not m:
        return None
    q = int(m.group(1)) if m.group(1).isdigit() else _NUM_WORDS[m.group(1)]
    months = q * 12 if m.group(2).startswith("ano") else q
    if m.group(3):
        months += 6 if m.group(2).startswith("ano") else 0
    return months if 1 <= months <= 600 else None


def _parse_day(n: str) -> Optional[int]:
    if re.search(r"ultimo dia|fim do mes|final do mes", n):
        return 31
    m = re.search(r"(?<!\d)(\d{1,2})(?!\d)", n)
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 31 else None


def _parse_start(n: str, today: date) -> Optional[Dict[str, Any]]:
    """«dezembro», «5 de dezembro», «dezembro de 2027», «próximo mês», «hoje» → {y, m, day?}."""
    if re.search(r"\b(?:hoje|agora|ja)\b", n):
        return {"y": today.year, "m": today.month, "day": today.day}
    if re.search(r"proximo mes|mes que vem|mes seguinte", n):
        d = _add_months(today, 1)
        return {"y": d.year, "m": d.month}
    m = re.search(rf"(?<!\d)(\d{{1,2}})\s+de\s+({_MESES_RE})(?:\s+de\s+(20\d{{2}}))?", n)
    day = None
    if m:
        day, mes, ano = int(m.group(1)), MESES[m.group(2)], m.group(3)
    else:
        m = re.search(rf"\b({_MESES_RE})\b(?:\s*(?:de|,)?\s*(20\d{{2}}))?", n)
        if not m:
            return None
        mes, ano = MESES[m.group(1)], m.group(2)
        dm = re.search(r"\bdia\s+(\d{1,2})\b", n)
        day = int(dm.group(1)) if dm else None
    y = int(ano) if ano else (today.year if mes >= today.month else today.year + 1)
    out: Dict[str, Any] = {"y": y, "m": mes}
    if day and 1 <= day <= 31:
        out["day"] = day
    return out


def _goal_question(step: str, s: Dict[str, Any]) -> str:
    if step == "kind":
        return "Que tipo de poupança queres? (casa, carro, viagem, estudos…)"
    if step == "target":
        ctx = _GOAL_CTX.get(s.get("icon_key", ""))
        return f"Quanto custa {ctx}?" if ctx else "Quanto queres juntar (em Kz)?"
    if step == "months":
        return "Durante quanto tempo pretendes guardar? (ex.: 12 meses)"
    if step == "start":
        return "Quando queres começar? (mês)"
    return "Em que dia do mês? (1 a 31)"


def _goal_ask(step: str, s: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    return _ask("CREATE_SAVINGS_GOAL", {**s, "ask": step}, prefix + _goal_question(step, s))


def _build_goal(slots: Dict[str, Any], today: date) -> Dict[str, Any]:
    """Constrói a meta passo a passo: tipo → valor → duração → início → dia. Uma pergunta de cada vez."""
    s = {k: v for k, v in slots.items() if k != "ask"}
    target = s.get("target")
    saved = float(s.get("saved") or 0)
    monthly = float(s.get("monthly") or 0)
    if not target:
        if (s.get("name") or "Nova meta") == "Nova meta" and s.get("icon_key", "target") == "target":
            return _goal_ask("kind", s, "Claro! ")
        return _goal_ask("target", s)
    remaining = max(0.0, float(target) - saved)
    months = s.get("months")
    deadline = s.get("deadline")  # [ano, mês]
    if not (months or deadline or monthly > 0):
        return _goal_ask("months", s)

    auto = s.get("auto", True)
    start_ym = s.get("start")      # [ano, mês]
    day = s.get("day")
    if auto and not start_ym:
        return _goal_ask("start", s)
    if auto and not day:
        return _goal_ask("day", s)

    first = None
    if auto:
        first = _clamp_day(start_ym[0], start_ym[1], int(day))
        note = ""
        if first < today:
            y, m = (first.year + (first.month == 12), first.month % 12 + 1)
            first = _clamp_day(y, m, int(day))
            note = f"O dia {day} já passou este mês, por isso começa em {_fmt_date(first)}."
        s["note"] = note or s.get("note", "")

    # --- duração e prestação ---
    if months:
        months = int(months)
    elif deadline:
        base = first or today
        months = (deadline[0] - base.year) * 12 + (deadline[1] - base.month) + (1 if first else 0)
        if months <= 0:
            s.pop("deadline", None)
            return _goal_ask("months", s, f"{MESES_NOME[deadline[1]]} de {deadline[0]} fica antes do início. ")
    else:
        months = max(1, math.ceil(remaining / monthly)) if remaining else 1
    if monthly <= 0:
        monthly = float(math.ceil(remaining / months)) if remaining else 0.0
    last = _add_months(first, months - 1) if first else _add_months(today, months)
    y, m = (last.year, last.month)
    icon, name = s.get("icon_key", "target"), s.get("name") or "Nova meta"
    action = {
        "type": "CREATE_SAVINGS_GOAL", "name": name, "icon_key": icon, "target": float(target), "saved": saved,
        "monthly": monthly, "deadline": f"{y:04d}-{m:02d}", "deadline_label": f"{MESES_NOME[m]} {y}",
        "months": months, "currency": "AOA",
    }
    lines = [f"**{name}** · {fmt_money(target)}", f"• {months} {'mês' if months == 1 else 'meses'} × **{fmt_money(monthly)}**/mês"]
    if first:
        action.update({"debit_day": int(day), "start_date": first.isoformat(), "start_label": _fmt_date(first)})
        lines.append(f"• 1.º débito: **{_fmt_date(first)}**, depois todo o dia {day}")
    lines.append(f"• Conclusão: {MESES_NOME[m]} {y}")
    if saved:
        lines.append(f"• Saldo inicial: {fmt_money(saved)} (sai já da conta)")
    reply = "Plano pronto:\n" + "\n".join(lines)
    if s.get("note"):
        reply += f"\n\n*{s['note']}*"
    reply += ("\n\nO valor sai da conta e fica em **Despesas**. A meta **ainda não foi criada**: "
              "toque em **Rever e criar meta** para confirmar.")
    return _done(action, reply)


def _goal_answer(text: str, n: str, prev: Dict[str, Any], today: date) -> Optional[Dict[str, Any]]:
    """Interpreta a resposta curta a uma pergunta do assistente de poupança («5», «dezembro», «15 meses»…)."""
    step = prev.get("ask")
    s = {k: v for k, v in prev.items() if k != "ask"}
    fresh = _parse_slots(text, today)
    ok = False
    if step == "kind":
        icon, name = _goal_icon_and_name(text, n)
        if name == "Nova meta":
            free = re.sub(r"^\W*(?:(?:uma?|de|do|da|para|pra|que|quero|poupanca|poupar|meta)\b\W*)+", "", text, flags=re.I).strip(" .,;!?")
            if 2 <= len(free) <= 40 and not re.search(r"\d", free):
                name = free[:1].upper() + free[1:]
        if name != "Nova meta":
            s["icon_key"], s["name"] = icon, name
            for k in ("target", "monthly", "saved"):
                if fresh.get(k):
                    s[k] = fresh[k]
            ok = True
    elif step == "target":
        if fresh.get("target"):
            s["target"] = fresh["target"]
            ok = True
    elif step == "months":
        months = _parse_months(n) or (int(n) if re.fullmatch(r"\W*(\d{1,3})\W*", n) else None)
        if months:
            s["months"] = months
            s.pop("deadline", None)
            ok = True
        elif fresh.get("deadline"):
            s["deadline"] = fresh["deadline"]
            ok = True
        elif fresh.get("monthly"):
            s["monthly"] = fresh["monthly"]
            ok = True
    elif step == "start":
        if _START_STOP.search(n):
            s["auto"] = False
            ok = True
        else:
            st = _parse_start(n, today)
            if st:
                s["start"] = [st["y"], st["m"]]
                if st.get("day"):
                    s["day"] = st["day"]
                ok = True
    elif step == "day":
        d = _parse_day(n)
        if d:
            s["day"] = d
            ok = True
    if ok:
        return _build_goal(s, today)
    if n.strip().endswith("?") or QUESTION_START.search(n):
        return None  # pergunta fora do assunto: segue para o modelo
    return _goal_ask(step, s, "Não percebi. ")


def _build_expense(slots: Dict[str, Any], today: date) -> Dict[str, Any]:
    amount = slots.get("amount")
    if not amount:
        return _ask("REGISTER_EXPENSE", slots, "Qual foi o valor da despesa (em Kz)?")
    cat = slots.get("category") or "Outros"
    name = slots.get("name") or f"Despesa em {cat}"
    iso = slots.get("date") or today.isoformat()
    action = {"type": "REGISTER_EXPENSE", "name": name, "category": cat, "amount": float(amount),
              "currency": "AOA", "date": iso, "notes": "Preparado pelo Copilot IA"}
    when = "hoje" if iso == today.isoformat() else \
        "ontem" if iso == (today - timedelta(days=1)).isoformat() else \
        "/".join(reversed(iso.split("-")))
    reply = (f"Despesa **{name}** · **{fmt_money(amount)}** ({cat}, {when}).\n"
             "Ainda **não foi registada**: toque em **Rever e registar**.")
    return _done(action, reply)


def _build_transfer_iban(slots: Dict[str, Any]) -> Dict[str, Any]:
    iban, amount = slots.get("to_iban"), slots.get("amount")
    if not iban:
        return _ask("TRANSFER_IBAN", slots, "Qual é o **IBAN** de destino?")
    if not amount:
        return _ask("TRANSFER_IBAN", slots, f"Quanto quer enviar para o IBAN `{iban}`?")
    cur = slots.get("currency") or "AOA"
    cc = iban[:2]
    fee, net = _fees(amount, FEE_IBAN)
    name = slots.get("beneficiary_name") or ""
    action = {
        "type": "TRANSFER_IBAN", "beneficiary_name": name, "to_iban": iban, "amount": float(amount), "currency": cur,
        "country_code": cc, "country_name": COUNTRY_MAP.get(cc, f"{cc} 🌐"), "fee_percent": FEE_IBAN, "fee_amount": fee,
        "net_amount": net, "dest_currency": "EUR" if cc in EUR_COUNTRIES else "AOA", "iban_valid": iban_ok(iban),
    }
    reply = (f"Transferência por **IBAN** · **{fmt_money(amount, cur)}** para `{iban}`"
             f"{' (' + name + ')' if name else ''}.\n"
             f"• Taxa ({FEE_IBAN:g}%): {fmt_money(fee, cur)} · Recebe: **{fmt_money(net, cur)}**")
    if not action["iban_valid"]:
        reply += "\n\n⚠️ Este IBAN não passa na validação (Mod 97). Confira os dígitos antes de avançar."
    if not name:
        reply += "\n\nFalta o **nome do beneficiário**: preencha-o no formulário."
    reply += "\n\nAinda **não foi enviada**: toque em **Rever e confirmar**."
    return _done(action, reply)


def _build_transfer_internal(slots: Dict[str, Any]) -> Dict[str, Any]:
    email, acc, amount = slots.get("to_email"), slots.get("to_account_number"), slots.get("amount")
    if not (email or acc):
        return _ask("TRANSFER_INTERNAL", slots, "Para que conta BankAO quer transferir? Indique o **e-mail do cliente** ou o **número da conta**.")
    dest = email or acc
    if not amount:
        return _ask("TRANSFER_INTERNAL", slots, f"Quanto quer transferir para `{dest}`?")
    cur = slots.get("currency") or "AOA"
    fee, net = _fees(amount, FEE_INTERNAL)
    name = slots.get("beneficiary_name") or ""
    action = {"type": "TRANSFER_INTERNAL", "to_email": email, "to_account_number": acc, "amount": float(amount),
              "currency": cur, "beneficiary_name": name, "fee_percent": FEE_INTERNAL, "fee_amount": fee, "net_amount": net}
    reply = (f"Transferência **BankAO** · **{fmt_money(amount, cur)}** para `{dest}`"
             f"{' (' + name + ')' if name else ''}.\n"
             f"• Taxa ({FEE_INTERNAL:g}%): {fmt_money(fee, cur)} · Recebe: **{fmt_money(net, cur)}**\n\n"
             "Ainda **não foi enviada**: toque em **Rever e confirmar**.")
    return _done(action, reply)


def _build_deposit(slots: Dict[str, Any]) -> Dict[str, Any]:
    phone, amount = slots.get("phone_number"), slots.get("amount")
    if not phone:
        return _ask("DEPOSIT_EXPRESS", slots, "Qual é o número de telemóvel associado ao **Multicaixa Express** (9xx xxx xxx)?")
    if not amount:
        return _ask("DEPOSIT_EXPRESS", slots, "Quanto quer depositar (em Kz)?")
    action = {"type": "DEPOSIT_EXPRESS", "phone_number": phone, "amount": float(amount), "currency": "AOA"}
    reply = (f"Depósito Express · **{fmt_money(amount)}** do número **{phone}**.\n"
             "Ainda **não foi enviado**: toque em **Rever e confirmar**.")
    return _done(action, reply)


BUILDERS = {
    "CREATE_SAVINGS_GOAL": lambda s, t: _build_goal(s, t),
    "REGISTER_EXPENSE": lambda s, t: _build_expense(s, t),
    "TRANSFER_IBAN": lambda s, t: _build_transfer_iban(s),
    "TRANSFER_INTERNAL": lambda s, t: _build_transfer_internal(s),
    "DEPOSIT_EXPRESS": lambda s, t: _build_deposit(s),
}


# ---------------------------------------------------------------------------
# Interpretação principal
# ---------------------------------------------------------------------------
def _parse_slots(text: str, today: date) -> Dict[str, Any]:
    """Extrai todos os dados que o texto contém, sem decidir a intenção."""
    text = normalize_spoken_text(text)
    n = _norm(text)
    slots: Dict[str, Any] = {}
    mask: List[Tuple[int, int]] = []

    ib = find_iban(text)
    if ib:
        slots["to_iban"] = ib[0]
        mask.append((ib[1], ib[2]))
    acc = find_account(_blank(text, mask))
    if acc:
        slots["to_account_number"] = acc[0]
        mask.append((acc[1], acc[2]))
    em = _EMAIL.search(text)
    if em:
        slots["to_email"] = em.group(0)
        mask.append(em.span())
    ph = _PHONE.search(_blank(text, mask))
    if ph and not ib:
        slots["phone_number"] = re.sub(r"\D", "", ph.group(1))
        mask.append(ph.span(1))

    st, st_spans = find_start(_blank(n, mask), today)
    if st:
        slots["start"] = [st["y"], st["m"]]
        if st.get("day"):
            slots["day"] = st["day"]
        mask.extend(st_spans)

    dl, dspans, note = find_deadline(_blank(n, mask), today)
    if dl:
        slots["deadline"] = list(dl)
        if note:
            slots["note"] = note
    mask.extend(dspans)

    n_masked = _blank(n, mask)
    amounts = find_amounts(n_masked)
    roles = {"initial": None, "monthly": None, "main": []}
    for a in amounts:
        r = _role(n_masked, a)
        if r == "main":
            roles["main"].append(a)
        elif roles[r] is None:
            roles[r] = a
    if roles["initial"]:
        slots["saved"] = roles["initial"]["value"]
    if roles["monthly"]:
        slots["monthly"] = roles["monthly"]["value"]
    main = _pick_main(roles["main"], min_bare=1.0)
    if main:
        slots["amount"] = main["value"]
        slots["target"] = main["value"]
        slots["_amount_span"] = list(main["span"])
        if main["currency"]:
            slots["currency"] = main["currency"]
    # moeda declarada noutro valor (ex.: "100 euros")
    if "currency" not in slots:
        for a in amounts:
            if a["currency"]:
                slots["currency"] = a["currency"]
                break

    if "hoje" in n:
        slots["date"] = today.isoformat()
    elif "anteontem" in n:
        slots["date"] = (today - timedelta(days=2)).isoformat()
    elif "ontem" in n:
        slots["date"] = (today - timedelta(days=1)).isoformat()

    bn = find_beneficiary(_blank(text, [s for s in mask if False]))
    if bn:
        slots["beneficiary_name"] = bn
    slots["_n"] = n
    return slots


def _detect_intent(n: str, slots: Dict[str, Any]) -> Optional[str]:
    # Prioridade para registo explícito de gasto ou despesa sobre criação de nova poupança.
    # Ex: "registre um gasto de 10mil na poupança de carro" -> REGISTER_EXPENSE (categoria Poupança)
    is_explicit_expense = bool(re.search(
        r"\b(?:registr?[aeo]r?|anot[aeo]r?|coloc[aeo]r?|adicion[aeo]r?)\s+(?:um\s+)?(?:gasto|despesa)\b|"
        r"\b(?:gastei|paguei)\b|"
        r"\bdespesa\s+de\b|"
        r"\bgasto\s+de\b",
        n
    ))
    if is_explicit_expense:
        return "REGISTER_EXPENSE"

    if SAVINGS_KW.search(n):
        return "CREATE_SAVINGS_GOAL"
    has_dest = bool(slots.get("to_iban") or slots.get("to_email") or slots.get("to_account_number"))
    if TRANSFER_KW.search(n) or (has_dest and re.search(r"\bpara\b", n)):
        if slots.get("to_iban") or re.search(r"\biban\b|internacional|portugal|europa|sepa|exterior|estrangeiro", n):
            return "TRANSFER_IBAN"
        if slots.get("to_email") or slots.get("to_account_number") or re.search(r"\bconta\b|entre contas|bankao|interna", n):
            return "TRANSFER_INTERNAL"
        return "TRANSFER"
    # «depósito a prazo» é um investimento, nunca um depósito por Multicaixa Express
    if DEPOSIT_KW.search(n) and not re.search(r"\bdepositos?\s+a\s+prazo\b", n) and (slots.get("phone_number") or slots.get("amount")):
        return "DEPOSIT_EXPRESS"

    # Perguntas analíticas e comparativas de gastos não são criação de novas despesas
    if re.search(r"\b(?:compar[ae]r?|onde\s+estou\s+a\s+gastar|analis[ae]r?|h[aá]bitos?|resumo\s+de\s+gastos?|quais\s+foram)\b", n):
        return None

    if EXPENSE_KW.search(n):
        # "tenho 20 mil de despesas?" é uma pergunta, não um pedido de registo
        if n.rstrip().endswith("?") and not re.search(r"\b(?:regist|anot|adicion|coloc|insir)\w*", n):
            return None
        return "REGISTER_EXPENSE"
    return None


def _is_question_without_data(n: str, slots: Dict[str, Any]) -> bool:
    has_data = any(k in slots for k in ("amount", "to_iban", "to_email", "to_account_number", "phone_number"))
    return (n.strip().endswith("?") or bool(QUESTION_START.search(n))) and not has_data


def _fill_slots(intent: str, slots: Dict[str, Any], text: str, today: date) -> Dict[str, Any]:
    """Completa os campos próprios de cada intenção (nome, categoria, ícone…)."""
    n = slots["_n"]
    out = {k: v for k, v in slots.items() if not k.startswith("_")}
    if intent not in TRANSFER_FAMILY:
        out.pop("beneficiary_name", None)
    if intent == "REGISTER_EXPENSE":
        said = explicit_category(n)
        out["category"] = said or detect_category(n)
        desc = text
        if slots.get("_amount_span"):
            desc = _blank(text, [tuple(slots["_amount_span"])])
        if said:   # tira «em eletrónicos» / «na categoria saúde» do nome da despesa
            desc = _CAT_PHRASE.sub(" ", desc)
        desc = re.sub(r"\b(?:kz|kzs|kwanzas?|aoa|akz)\b", " ", desc, flags=re.I)
        desc = re.sub(r"\b(?:hoje|ontem|anteontem)\b", " ", desc, flags=re.I)
        prev = None
        while prev != desc:
            prev = desc
            desc = re.sub(r"^\W*(?:por\s+favor|registr?[aeo](?:r)?|anot[aeo](?:r)?|adicion[aeo](?:r)?|coloc[aeo](?:r)?|insir[aeo]?|inserir?|gastei|paguei|comprei|"
                          r"despesa|gasto|uma|um|de|em|no|na|nos|nas|com|para|do|da|o|a|e)\b", " ", desc, flags=re.I)
        prev = None
        while prev != desc:   # sobras no fim: «telefone de», «café a»
            prev = desc
            desc = re.sub(r"\s+(?:de|do|da|dos|das|em|no|na|nos|nas|a|ao|para|com|por|que|e)\W*$", " ", desc, flags=re.I)
        desc = re.sub(r"\s+", " ", desc).strip(" .,;:-")
        if len(desc) < 3:
            desc = f"Despesa em {out['category']}"
        out["name"] = desc[:1].upper() + desc[1:]
    elif intent == "CREATE_SAVINGS_GOAL":
        icon, name = _goal_icon_and_name(text, n)
        out["icon_key"], out["name"] = icon, name
    return out


SLOT_KEYS = {"amount", "target", "to_iban", "to_email", "to_account_number", "phone_number", "deadline",
             "saved", "monthly", "beneficiary_name", "date", "currency", "start", "day"}
TRANSFER_FAMILY = {"TRANSFER", "TRANSFER_IBAN", "TRANSFER_INTERNAL"}


def _transfer_kind(merged: Dict[str, Any], fresh: Dict[str, Any], n: str, current: str) -> str:
    """Decide entre IBAN e conta BankAO com o que o utilizador acabou de dizer; só depois com o que já se sabia."""
    if fresh.get("to_iban"):
        return "TRANSFER_IBAN"
    if fresh.get("to_email") or fresh.get("to_account_number"):
        return "TRANSFER_INTERNAL"
    if re.search(r"\biban\b|internacional|portugal|europa|sepa|exterior|estrangeiro", n):
        return "TRANSFER_IBAN"
    if re.search(r"\bconta\b|entre contas|bankao|\be-?mail\b|interna", n):
        return "TRANSFER_INTERNAL"
    if current != "TRANSFER":
        return current
    if merged.get("to_iban"):
        return "TRANSFER_IBAN"
    if merged.get("to_email") or merged.get("to_account_number"):
        return "TRANSFER_INTERNAL"
    return "TRANSFER"


def analyze_message(message: str, pending: Optional[Dict[str, Any]] = None, today: Optional[date] = None) -> Dict[str, Any]:
    """
    Resultado: {"action": dict|None, "reply": str|None, "pending": dict|None}
      • action  → dados prontos para pré-preencher um formulário (o utilizador conclui).
      • reply   → texto determinístico (pergunta ou resumo). None = deixar o modelo conversar.
      • pending → intenção a meio (falta um dado) — o frontend devolve-a na mensagem seguinte.
    """
    today = today or date.today()
    text = normalize_spoken_text((message or "").strip())
    if not text:
        return {"action": None, "reply": None, "pending": None}
    slots = _parse_slots(text, today)
    n = slots["_n"]
    intent = _detect_intent(n, slots)

    prev_type = pending.get("type") if isinstance(pending, dict) else None
    prev_slots = pending.get("slots") if isinstance(pending, dict) else None

    # --- Resposta a uma pergunta anterior: junta o que já se sabia com o que chegou agora ---
    if prev_type and isinstance(prev_slots, dict):
        if re.search(r"^\W*(?:nao|esquece|cancela|deixa)\b|\bcancela\b|\bnao quero\b", n) and not (
                prev_slots.get("ask") == "start" and _START_STOP.search(n)):
            return {"action": None, "reply": "Sem problema, cancelei o pedido. Em que mais posso ajudar?", "pending": None}
        if prev_type == "CREATE_SAVINGS_GOAL" and prev_slots.get("ask"):
            res = _goal_answer(text, n, prev_slots, today)
            if res is not None:
                return res
        same_family = (intent is None or intent == prev_type or
                       (intent in TRANSFER_FAMILY and prev_type in TRANSFER_FAMILY))
        if same_family:
            fresh = _fill_slots(prev_type, slots, text, today)
            if prev_type != "CREATE_SAVINGS_GOAL" and prev_type != "REGISTER_EXPENSE":
                fresh.pop("name", None)
            gained = any(k in SLOT_KEYS and fresh.get(k) not in (None, "") and fresh.get(k) != prev_slots.get(k)
                         for k in fresh) or (prev_type in TRANSFER_FAMILY and
                                             bool(re.search(r"iban|\bconta\b|internacional|bankao|e-?mail", n)))
            if gained:
                kind = _transfer_kind({**prev_slots, **fresh}, fresh, n, prev_type) if prev_type in TRANSFER_FAMILY else prev_type
                # ao responder só com o prazo/valor, mantém o nome/ícone já descobertos
                if prev_type in ("CREATE_SAVINGS_GOAL", "REGISTER_EXPENSE"):
                    for k in ("name", "icon_key", "category"):
                        if prev_slots.get(k) and not (intent == prev_type):
                            fresh.pop(k, None)
                merged = {**prev_slots, **{k: v for k, v in fresh.items() if v not in (None, "")}}
                if kind != "CREATE_SAVINGS_GOAL":
                    merged.pop("target", None)
                if kind == "TRANSFER":
                    return _ask("TRANSFER", merged, "Quer transferir para uma **conta BankAO** (e-mail ou nº de conta) ou para um **IBAN**?")
                return BUILDERS[kind](merged, today)
        # não respondeu à pergunta: abandona o pedido pendente e trata a mensagem normalmente

    wants_goal = intent == "CREATE_SAVINGS_GOAL" and re.search(
        r"\b(?:quero|queria|gostaria|criar|crie|abrir|fazer|iniciar|comecar|definir|nova)\b|como (?:eu )?(?:faco|crio|abro|posso)", n)
    if intent is None or (_is_question_without_data(n, slots) and not wants_goal):
        return {"action": None, "reply": None, "pending": None}

    filled = _fill_slots(intent, slots, text, today)
    if intent == "TRANSFER":
        return _ask("TRANSFER", filled, "Quer transferir para uma **conta BankAO** (e-mail ou nº de conta) ou para um **IBAN**? Diga-me também o valor.")
    if intent != "CREATE_SAVINGS_GOAL":
        filled.pop("target", None)
    return BUILDERS[intent](filled, today)


# ---------------------------------------------------------------------------
# Compatibilidade: ação vinda do modelo (validada) ou do interpretador
# ---------------------------------------------------------------------------
def _validate_llm_action(data: Any, today: date) -> Optional[Dict[str, Any]]:
    """Aceita o bloco JSON do modelo só se for coerente; refaz os cálculos e nunca confia em taxas/valores derivados."""
    if not isinstance(data, dict):
        return None
    t = data.get("type")
    try:
        amount = float(data.get("amount") or data.get("target") or 0)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    if t == "TRANSFER_IBAN" and data.get("to_iban"):
        return _build_transfer_iban({"to_iban": str(data["to_iban"]).replace(" ", "").upper(), "amount": amount,
                                     "currency": data.get("currency") or "AOA",
                                     "beneficiary_name": str(data.get("beneficiary_name") or "")}).get("action")
    if t == "TRANSFER_INTERNAL" and (data.get("to_email") or data.get("to_account_number")):
        return _build_transfer_internal({"to_email": data.get("to_email"), "to_account_number": data.get("to_account_number"),
                                         "amount": amount, "currency": data.get("currency") or "AOA",
                                         "beneficiary_name": str(data.get("beneficiary_name") or "")}).get("action")
    if t == "REGISTER_EXPENSE":
        cat = data.get("category") if data.get("category") in CATEGORIAS else "Outros"
        return _build_expense({"amount": amount, "category": cat, "name": str(data.get("name") or "")[:120]}, today).get("action")
    return None


def extract_action_intent(message: str, ai_content: str = "", pending: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Devolve só a ação pronta (ou None). O interpretador determinístico tem prioridade sobre o modelo."""
    res = analyze_message(message, pending)
    if res["action"]:
        return res["action"]
    if res["pending"]:
        return None
    if ai_content:
        m = re.search(r"```(?:json:action|json)\s*(\{.*?\})\s*```", ai_content, re.DOTALL)
        if m:
            try:
                return _validate_llm_action(json.loads(m.group(1)), date.today())
            except Exception:
                return None
    return None


def analyze_action_reply(action: Dict[str, Any]) -> str:
    """Texto honesto para uma ação já validada (usado quando a ação veio do modelo)."""
    t = action.get("type")
    today = date.today()
    if t == "TRANSFER_IBAN":
        return _build_transfer_iban({"to_iban": action["to_iban"], "amount": action["amount"], "currency": action.get("currency"),
                                     "beneficiary_name": action.get("beneficiary_name")})["reply"]
    if t == "TRANSFER_INTERNAL":
        return _build_transfer_internal({"to_email": action.get("to_email"), "to_account_number": action.get("to_account_number"),
                                         "amount": action["amount"], "currency": action.get("currency"),
                                         "beneficiary_name": action.get("beneficiary_name")})["reply"]
    if t == "REGISTER_EXPENSE":
        return _build_expense({"amount": action["amount"], "category": action.get("category"), "name": action.get("name")}, today)["reply"]
    return "Preparei o pedido. Reveja os dados e confirme."
