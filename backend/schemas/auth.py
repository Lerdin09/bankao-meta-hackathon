"""
Modelos Pydantic — Autenticação e registo.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    telefone: str
    password: str = Field(..., min_length=6)
    confirm_password: Optional[str] = None
    terms_accepted: bool = Field(default=True)
    nome: Optional[str] = "Novo Utilizador"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
