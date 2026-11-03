"""
Rotas — Contactos: pessoas (clientes BankAO) e IBANs com quem o utilizador já movimentou dinheiro,
mais os contactos que guardou (apelido, favorito). Serve para reenviar dinheiro com um toque.

O histórico (tabela `transfers`) é lido sempre que se lista: quem enviou/recebeu aparece automaticamente
como contacto «sugerido» (saved = false). Guardar só acrescenta apelido/favorito.
Privacidade: nunca se expõe o e-mail de terceiros; do cliente BankAO só nome e nº de conta (que o
próprio utilizador já viu ao transacionar).
"""
import re
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.core.security import get_current_user
from backend.database import get_connection
from backend.database.connection import transaction_scope
from backend.schemas import ContactSave, ContactUpdate
from backend.services.iban import iban_valido

router = APIRouter(prefix="/api/contacts", tags=["Contactos"])


def _nome(u) -> str:
    nome = u["nome"]
    if not nome or nome == "Novo Utilizador":
        nome = f"{u['primeiro_nome'] or ''} {u['ultimo_nome'] or ''}".strip() or "Cliente BankAO"
    return nome


def _clean_iban(v: str) -> str:
    return re.sub(r"\s+", "", v or "").upper()


def _public(c: Dict[str, Any]) -> Dict[str, Any]:
    c["display_name"] = c.get("nickname") or c["name"]
    c["total_count"] = c["sent_count"] + c["received_count"]
    return c


def _history(conn, user_id: str) -> Dict[str, Dict[str, Any]]:
    """Contrapartes do histórico de transferências concluídas, agrupadas por ref_key."""
    found: Dict[str, Dict[str, Any]] = {}

    def touch(key: str, base: Dict[str, Any], direction: str, row) -> None:
        # As linhas chegam por ordem cronológica (ORDER BY created_at): a última tocada é a mais recente.
        c = found.setdefault(key, {
            **base, "sent_count": 0, "received_count": 0, "last_at": None,
            "last_direction": None, "last_sent_amount": None, "last_sent_currency": None,
        })
        c["sent_count" if direction == "sent" else "received_count"] += 1
        if c["last_at"] is None or str(row["created_at"]) >= str(c["last_at"]):
            c["last_at"], c["last_direction"] = row["created_at"], direction
        if direction == "sent":
            c["last_sent_amount"] = row["source_amount_minor"] / 100.0
            c["last_sent_currency"] = row["source_currency"]

    # Enviadas para clientes BankAO
    for r in conn.execute("""
        SELECT t.created_at, t.source_amount_minor, t.source_currency,
               a2.account_number, u.id AS uid, u.nome, u.primeiro_nome, u.ultimo_nome
        FROM transfers t
        JOIN accounts a1 ON a1.id = t.from_account_id
        JOIN accounts a2 ON a2.id = t.to_account_id
        JOIN users u ON u.id = a2.user_id
        WHERE a1.user_id = ? AND a2.user_id != ? AND t.status = 'completed'
        ORDER BY t.created_at
    """, (user_id, user_id)):
        touch(f"u:{r['uid']}", {"kind": "internal", "name": _nome(r), "account_number": r["account_number"], "iban": None}, "sent", r)

    # Recebidas de clientes BankAO
    for r in conn.execute("""
        SELECT t.created_at, t.source_amount_minor, t.source_currency,
               a1.account_number, u.id AS uid, u.nome, u.primeiro_nome, u.ultimo_nome
        FROM transfers t
        JOIN accounts a1 ON a1.id = t.from_account_id
        JOIN accounts a2 ON a2.id = t.to_account_id
        JOIN users u ON u.id = a1.user_id
        WHERE a2.user_id = ? AND a1.user_id != ? AND t.status = 'completed'
        ORDER BY t.created_at
    """, (user_id, user_id)):
        touch(f"u:{r['uid']}", {"kind": "internal", "name": _nome(r), "account_number": r["account_number"], "iban": None}, "received", r)

    # Enviadas por IBAN
    for r in conn.execute("""
        SELECT t.created_at, t.source_amount_minor, t.source_currency, t.to_iban, t.beneficiary_name
        FROM transfers t
        JOIN accounts a1 ON a1.id = t.from_account_id
        WHERE a1.user_id = ? AND t.to_account_id IS NULL AND t.to_iban IS NOT NULL AND t.status = 'completed'
        ORDER BY t.created_at
    """, (user_id,)):
        iban = _clean_iban(r["to_iban"])
        touch(f"i:{iban}", {"kind": "iban", "name": r["beneficiary_name"], "account_number": None, "iban": iban}, "sent", r)

    return found


def _build_list(user_id: str) -> list:
    with get_connection() as conn:
        hist = _history(conn, user_id)
        saved = {r["ref_key"]: r for r in conn.execute("SELECT * FROM contacts WHERE user_id = ?", (user_id,))}

    out = []
    for key in set(hist) | set(saved):
        h = hist.get(key)
        s = saved.get(key)
        c = {
            "id": s["id"] if s else None,
            "key": key,
            "saved": bool(s),
            "kind": (s or h)["kind"],
            "name": h["name"] if (h and h["kind"] == "internal") else (s or h)["name"],
            "nickname": s["nickname"] if s else None,
            "account_number": (s["account_number"] if s else None) or (h or {}).get("account_number"),
            "iban": (s["iban"] if s else None) or (h or {}).get("iban"),
            "favorite": bool(s["favorite"]) if s else False,
            "sent_count": (h or {}).get("sent_count", 0),
            "received_count": (h or {}).get("received_count", 0),
            "last_at": (h or {}).get("last_at"),
            "last_direction": (h or {}).get("last_direction"),
            "last_sent_amount": (h or {}).get("last_sent_amount"),
            "last_sent_currency": (h or {}).get("last_sent_currency"),
        }
        out.append(_public(c))
    # Ordem: favoritos primeiro, depois o mais recente; sem histórico no fim; desempate por nome.
    out.sort(key=lambda c: c["display_name"].lower())
    out.sort(key=lambda c: c["last_at"] or "", reverse=True)
    out.sort(key=lambda c: not c["favorite"])
    return out


@router.get("")
def list_contacts(q: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    items = _build_list(current_user["id"])
    if q and q.strip():
        needle = q.strip().lower()
        needle_digits = re.sub(r"\W", "", needle)
        def hit(c):
            hay = " ".join(filter(None, [c["name"], c["nickname"], c["account_number"], c["iban"]])).lower()
            return needle in hay or (needle_digits and needle_digits in re.sub(r"\W", "", hay))
        items = [c for c in items if hit(c)]
    return {"contacts": items, "total": len(items)}


@router.get("/history")
def contact_history(key: str, limit: int = 10, offset: int = 0, current_user: dict = Depends(get_current_user)):
    """
    Transferências concluídas entre o utilizador e um contacto (`key` = 'u:<id>' ou 'i:<IBAN>'),
    da mais recente para a mais antiga, em páginas (`limit`/`offset`).
    Cada linha traz o valor que mexeu na conta do utilizador e o saldo dessa conta antes e depois
    (soma acumulada do livro-razão até esse lançamento).
    """
    uid = current_user["id"]
    limit = max(1, min(int(limit), 50))
    offset = max(0, int(offset))

    if key.startswith("u:"):
        cp = key[2:]
        if not cp or cp == uid:
            raise HTTPException(status_code=422, detail="Contacto inválido.")
        where = "t.status = 'completed' AND ((fa.user_id = ? AND ta.user_id = ?) OR (fa.user_id = ? AND ta.user_id = ?))"
        params: list = [uid, cp, cp, uid]
        joins = "JOIN accounts fa ON fa.id = t.from_account_id JOIN accounts ta ON ta.id = t.to_account_id"
        mine = "CASE WHEN fa.user_id = ? THEN fa.id ELSE ta.id END"
        mine_params: list = [uid]
        method = "Entre contas BankAO"
    elif key.startswith("i:"):
        iban = _clean_iban(key[2:])
        if not iban:
            raise HTTPException(status_code=422, detail="Contacto inválido.")
        where = ("t.status = 'completed' AND fa.user_id = ? AND t.to_account_id IS NULL "
                 "AND replace(upper(t.to_iban), ' ', '') = ?")
        params = [uid, iban]
        joins = "JOIN accounts fa ON fa.id = t.from_account_id"
        mine = "fa.id"
        mine_params = []
        method = "Transferência por IBAN"
    else:
        raise HTTPException(status_code=422, detail="Contacto inválido.")

    base = f"""
        FROM transfers t {joins}
        JOIN ledger_entries e ON e.transaction_id = t.transaction_id AND e.account_id = {mine}
        WHERE {where}
    """
    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n {base}", mine_params + params).fetchone()["n"]
        rows = conn.execute(f"""
            SELECT t.id, t.created_at, t.beneficiary_name, t.fee_minor, t.dest_currency,
                   t.source_amount_minor, t.dest_amount_minor,
                   e.amount_minor AS my_amount, e.currency AS my_currency,
                   (SELECT COALESCE(SUM(x.amount_minor), 0) FROM ledger_entries x
                     WHERE x.account_id = e.account_id AND x.id <= e.id) AS balance_after
            {base}
            ORDER BY e.id DESC
            LIMIT ? OFFSET ?
        """, mine_params + params + [limit, offset]).fetchall()

        names = {}
        if key.startswith("u:"):
            u = conn.execute("SELECT nome, primeiro_nome, ultimo_nome FROM users WHERE id = ?", (key[2:],)).fetchone()
            names["cp"] = _nome(u) if u else "Cliente BankAO"

    items = []
    for r in rows:
        sent = r["my_amount"] < 0
        after = r["balance_after"]
        items.append({
            "id": r["id"],
            "direction": "sent" if sent else "received",
            "name": names.get("cp") or r["beneficiary_name"],
            "amount": abs(r["my_amount"]) / 100.0,
            "currency": r["my_currency"],
            "created_at": r["created_at"],
            "method": method,
            "balance_before": (after - r["my_amount"]) / 100.0,
            "balance_after": after / 100.0,
            "fee": (r["fee_minor"] or 0) / 100.0,
        })
    return {"items": items, "total": total, "offset": offset, "limit": limit, "has_more": offset + len(items) < total}


@router.post("")
def save_contact(data: ContactSave, current_user: dict = Depends(get_current_user)):
    """Guarda (ou atualiza) um contacto. Idempotente por destinatário."""
    uid = current_user["id"]
    nickname = (data.nickname or "").strip() or None

    with get_connection() as conn:
        if data.kind == "internal":
            digits = re.sub(r"\D", "", data.account_number or "")
            if not digits:
                raise HTTPException(status_code=422, detail="Indique o número de conta do cliente.")
            row = conn.execute(
                "SELECT a.account_number, u.id AS uid, u.nome, u.primeiro_nome, u.ultimo_nome "
                "FROM accounts a JOIN users u ON u.id = a.user_id WHERE a.account_number = ?", (digits,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Conta BankAO não encontrada.")
            if row["uid"] == uid:
                raise HTTPException(status_code=400, detail="Não pode guardar a sua própria conta como contacto.")
            key, name, account_number, iban = f"u:{row['uid']}", _nome(row), row["account_number"], None
        else:
            iban = _clean_iban(data.iban or "")
            if not iban_valido(iban):
                raise HTTPException(status_code=422, detail="IBAN inválido (falhou a validação Mod 97).")
            name = (data.name or "").strip()
            if len(name) < 3:
                raise HTTPException(status_code=422, detail="Indique o nome do titular (mín. 3 letras).")
            own = conn.execute(
                "SELECT 1 FROM accounts WHERE user_id = ? AND replace(upper(iban_virtual), ' ', '') = ?", (uid, iban)
            ).fetchone()
            if own:
                raise HTTPException(status_code=400, detail="Esse IBAN pertence a uma das suas contas.")
            key, account_number = f"i:{iban}", None

    with transaction_scope() as conn:
        existing = conn.execute("SELECT id, favorite FROM contacts WHERE user_id = ? AND ref_key = ?", (uid, key)).fetchone()
        fav = int(data.favorite) if data.favorite is not None else (existing["favorite"] if existing else 0)
        if existing:
            conn.execute(
                "UPDATE contacts SET name = ?, nickname = COALESCE(?, nickname), favorite = ?, account_number = ?, iban = ? WHERE id = ?",
                (name, nickname, fav, account_number, iban, existing["id"]),
            )
            cid = existing["id"]
        else:
            cid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO contacts (id, user_id, kind, ref_key, name, nickname, account_number, iban, favorite) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, uid, data.kind, key, name, nickname, account_number, iban, fav),
            )
    return next(c for c in _build_list(uid) if c["id"] == cid)


@router.patch("/{contact_id}")
def update_contact(contact_id: str, data: ContactUpdate, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    with transaction_scope() as conn:
        row = conn.execute("SELECT id FROM contacts WHERE id = ? AND user_id = ?", (contact_id, uid)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contacto não encontrado.")
        fields = data.model_dump(exclude_unset=True)
        if "nickname" in fields:
            conn.execute("UPDATE contacts SET nickname = ? WHERE id = ?", ((fields["nickname"] or "").strip() or None, contact_id))
        if "favorite" in fields and fields["favorite"] is not None:
            conn.execute("UPDATE contacts SET favorite = ? WHERE id = ?", (int(fields["favorite"]), contact_id))
    return next(c for c in _build_list(uid) if c["id"] == contact_id)


@router.delete("/{contact_id}")
def delete_contact(contact_id: str, current_user: dict = Depends(get_current_user)):
    """Remove dos guardados. Se houver histórico com essa pessoa/IBAN, continua a aparecer como sugerido."""
    with transaction_scope() as conn:
        cur = conn.execute("DELETE FROM contacts WHERE id = ? AND user_id = ?", (contact_id, current_user["id"]))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contacto não encontrado.")
    return {"deleted": True}
