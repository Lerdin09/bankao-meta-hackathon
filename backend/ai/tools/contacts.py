"""
Ferramentas de Contactos para a IA do BankAO.
Permite consultar contactos guardados, destinatários frequentes e detalhes de pagamento.
"""
from typing import Any, Dict, List, Optional


import unicodedata

def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    # Remove acentos e caracteres especiais para busca robusta (ex: irmão -> irmao)
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def tool_get_contacts(
    user_id: str,
    query: Optional[str] = None,
    favorites_only: bool = False,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Lista os contactos e destinatários frequentes do cliente.
    Suporta pesquisa por nome, apelido, número de conta ou IBAN.
    """
    from backend.api.routes.contacts import _build_list

    contacts = _build_list(user_id)

    if favorites_only:
        contacts = [c for c in contacts if c.get("favorite")]

    if query and query.strip():
        q = _normalize(query.strip())
        filtered = []
        for c in contacts:
            name_match = q in _normalize(c.get("name"))
            nick_match = q in _normalize(c.get("nickname"))
            disp_match = q in _normalize(c.get("display_name"))
            acc_match = q in _normalize(c.get("account_number"))
            iban_match = q in _normalize(c.get("iban"))
            if name_match or nick_match or disp_match or acc_match or iban_match:
                filtered.append(c)
        contacts = filtered

    contacts = contacts[:limit]

    return {
        "total_found": len(contacts),
        "contacts": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "nickname": c.get("nickname"),
                "display_name": c.get("display_name"),
                "kind": c.get("kind"),
                "account_number": c.get("account_number"),
                "iban": c.get("iban"),
                "favorite": c.get("favorite", False),
                "saved": c.get("saved", False),
                "sent_count": c.get("sent_count", 0),
                "received_count": c.get("received_count", 0),
                "last_at": c.get("last_at"),
                "last_sent_amount": c.get("last_sent_amount"),
                "last_sent_currency": c.get("last_sent_currency")
            }
            for c in contacts
        ]
    }
