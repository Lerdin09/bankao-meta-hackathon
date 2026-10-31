"""
Rotas — IBAN: Validação de IBAN (Mod 97).
"""

from fastapi import APIRouter

from backend.services.iban import formatar_iban, iban_valido

router = APIRouter(prefix="/api/iban", tags=["IBAN"])


@router.get("/validate")
def validate_iban(iban: str):
    valid = iban_valido(iban)
    clean = iban.replace(" ", "").upper()
    country = clean[:2] if len(clean) >= 2 else ""
    return {
        "iban": clean,
        "formatted": formatar_iban(clean) if clean else "",
        "valid": valid,
        "country": country,
        "note": "Validação matemática de controle Mod 97."
    }
