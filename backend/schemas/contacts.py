"""
Modelos Pydantic — Contactos (pessoas e IBANs guardados para reenvio rápido).
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class ContactSave(BaseModel):
    kind: Literal["internal", "iban"]
    account_number: Optional[str] = None   # obrigatório se kind == "internal"
    iban: Optional[str] = None             # obrigatório se kind == "iban"
    name: Optional[str] = Field(default=None, max_length=120)      # obrigatório para IBAN
    nickname: Optional[str] = Field(default=None, max_length=60)
    favorite: Optional[bool] = None


class ContactUpdate(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=60)
    favorite: Optional[bool] = None
