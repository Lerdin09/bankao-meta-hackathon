"""
Rotas — Autenticação: Registo, login e dados do utilizador autenticado.
"""

import datetime
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.core.security import create_access_token, get_current_user, get_password_hash, verify_password
from backend.database import get_connection
from backend.schemas import TokenResponse, UserLogin, UserRegister
from backend.services.iban import gerar_iban_ficticio

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])


@router.post("/register", response_model=TokenResponse)
def register(data: UserRegister):
    if data.confirm_password and data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="As palavras-passe não coincidem.")
    if not data.terms_accepted:
        raise HTTPException(status_code=400, detail="Deve aceitar os Termos e Condições para criar conta.")

    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Este e-mail já está registado. Por favor inicie sessão.")

        user_id = str(uuid.uuid4())
        pwd_hash = get_password_hash(data.password)
        nome_display = data.nome if (data.nome and data.nome != "Novo Utilizador") else "Novo Utilizador"

        conn.execute(
            """
            INSERT INTO users (id, nome, email, password_hash, telefone, kyc_status, terms_accepted)
            VALUES (?, ?, ?, ?, ?, 'pendente', 1)
            """,
            (user_id, nome_display, data.email, pwd_hash, data.telefone)
        )

        # Criar automaticamente 3 cartões/contas: AO (Angola - AOA), PT (Portugal - EUR) e US (Estados Unidos - USD) com saldo 0
        acc_aoa_id = str(uuid.uuid4())
        acc_aoa_num = f"0040{random.randint(10000000, 99999999)}"
        iban_aoa = gerar_iban_ficticio("AO")
        conn.execute(
            "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'AOA')",
            (acc_aoa_id, user_id, acc_aoa_num, iban_aoa)
        )

        acc_eur_id = str(uuid.uuid4())
        acc_eur_num = f"0050{random.randint(10000000, 99999999)}"
        iban_eur = gerar_iban_ficticio("PT")
        conn.execute(
            "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'EUR')",
            (acc_eur_id, user_id, acc_eur_num, iban_eur)
        )

        acc_usd_id = str(uuid.uuid4())
        acc_usd_num = f"0060{random.randint(10000000, 99999999)}"
        iban_usd = gerar_iban_ficticio("US")
        conn.execute(
            "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'USD')",
            (acc_usd_id, user_id, acc_usd_num, iban_usd)
        )

    token = create_access_token(data={"sub": user_id, "email": data.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "nome": nome_display,
            "email": data.email,
            "telefone": data.telefone,
            "kyc_status": "pendente",
            "created_at": datetime.datetime.utcnow().isoformat()
        }
    }


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin):
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (data.email,)).fetchone()
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="E-mail ou palavra-passe incorretos.")

        user_dict = {
            "id": user["id"],
            "nome": user["nome"],
            "primeiro_nome": user["primeiro_nome"],
            "ultimo_nome": user["ultimo_nome"],
            "email": user["email"],
            "telefone": user["telefone"],
            "kyc_status": user["kyc_status"],
            "doc_tipo": user["doc_tipo"],
            "doc_numero": user["doc_numero"],
            "created_at": user["created_at"] if "created_at" in user.keys() else None
        }

    token = create_access_token(data={"sub": user["id"], "email": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_dict
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
