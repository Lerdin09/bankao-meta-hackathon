"""
Aplicação Principal FastAPI — Bankão (Meta Global AI Developer Hackathon).
"""
import uuid
import random
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.config import settings
from app.db import init_db, get_connection, transaction_scope
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.iban import gerar_iban_ficticio, iban_valido, formatar_iban
from app.ledger import (
    get_user_accounts,
    get_account_balance,
    execute_internal_transfer,
    credit_deposit,
    InsufficientFundsError,
    AccountNotFoundError
)
from app.providers.deposits import DepositProvider
from app.providers.fx import FXProvider
from app.providers.payout import PayoutProvider
from app.ai.assistant import BankaoAssistant
from app.schemas import (
    UserRegister, UserLogin, TokenResponse,
    DepositReferenciaCreate, DepositExpressCreate, DepositSimulatePayment,
    InternalTransferCreate, IbanTransferCreate, FxQuoteRequest,
    AIChatRequest, AIExplainTransferRequest
)

# Inicializar Base de Dados e tabelas do livro-razão
init_db()

app = FastAPI(
    title="Bankão API",
    description="Carteira Digital para Angola e o Mundo — Meta Global AI Developer Hackathon",
    version="1.0.0"
)

# Habilitar CORS para permitir testes flexíveis no navegador
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- ROTAS DE AUTENTICAÇÃO -----------------

@app.post("/api/auth/register", response_model=TokenResponse)
def register(data: UserRegister):
    with get_connection() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Este e-mail já está registrado.")

        user_id = str(uuid.uuid4())
        pwd_hash = get_password_hash(data.password)

        conn.execute(
            """
            INSERT INTO users (id, nome, email, password_hash, telefone, kyc_status)
            VALUES (?, ?, ?, ?, ?, 'verificado')
            """,
            (user_id, data.nome, data.email, pwd_hash, data.telefone)
        )

        # Criar automaticamente carteira em Kwanza (AOA) e Euro (EUR)
        # Conta AOA
        acc_aoa_id = str(uuid.uuid4())
        acc_aoa_num = f"0040{random.randint(10000000, 99999999)}"
        iban_aoa = gerar_iban_ficticio("AO")
        conn.execute(
            "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'AOA')",
            (acc_aoa_id, user_id, acc_aoa_num, iban_aoa)
        )

        # Conta EUR
        acc_eur_id = str(uuid.uuid4())
        acc_eur_num = f"0050{random.randint(10000000, 99999999)}"
        iban_eur = gerar_iban_ficticio("PT")
        conn.execute(
            "INSERT INTO accounts (id, user_id, account_number, iban_virtual, currency) VALUES (?, ?, ?, ?, 'EUR')",
            (acc_eur_id, user_id, acc_eur_num, iban_eur)
        )

        # Bônus de boas-vindas simulado para testes imediatos (100.000 Kz)
        tx_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO transactions (id, type, status, description) VALUES (?, 'deposit', 'completed', 'Bónus de Boas-Vindas Sandbox')",
            (tx_id,)
        )
        conn.execute(
            "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, 10000000, 'AOA')",
            (tx_id, acc_aoa_id)
        )

    token = create_access_token(data={"sub": user_id, "email": data.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "nome": data.nome,
            "email": data.email,
            "telefone": data.telefone,
            "kyc_status": "verificado"
        }
    }

@app.post("/api/auth/login", response_model=TokenResponse)
def login(data: UserLogin):
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (data.email,)).fetchone()
        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="E-mail ou palavra-passe incorretos.")

        user_dict = {
            "id": user["id"],
            "nome": user["nome"],
            "email": user["email"],
            "telefone": user["telefone"],
            "kyc_status": user["kyc_status"]
        }

    token = create_access_token(data={"sub": user["id"], "email": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_dict
    }

@app.get("/api/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user

# ----------------- CONTAS & CARTEIRAS -----------------

@app.get("/api/accounts")
def get_accounts(current_user: dict = Depends(get_current_user)):
    accounts = get_user_accounts(current_user["id"])
    return accounts

# ----------------- DEPÓSITOS -----------------

@app.post("/api/deposits/referencia")
def criar_deposito_referencia(
    data: DepositReferenciaCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    res = DepositProvider.criar_deposito_referencia(data.account_id, amount_minor, "AOA")
    return res

@app.post("/api/deposits/multicaixa-express")
def criar_deposito_multicaixa_express(
    data: DepositExpressCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    res = DepositProvider.criar_deposito_multicaixa_express(data.account_id, amount_minor, data.phone_number, "AOA")
    return res

@app.post("/api/deposits/simulate-payment")
def simular_pagamento(data: DepositSimulatePayment):
    """Simula a confirmação de pagamento do Multicaixa Express ou Referência."""
    try:
        result = credit_deposit(data.deposit_id)
        return {
            "success": True,
            "message": "Pagamento confirmado com sucesso! Saldo creditado na sua carteira.",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- TRANSFERÊNCIAS -----------------

@app.post("/api/transfers/internal")
def transfer_internal(
    data: InternalTransferCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))

    # Descobrir a conta de destino pelo número da conta
    with get_connection() as conn:
        dest = conn.execute("SELECT id FROM accounts WHERE account_number = ?", (data.to_account_number,)).fetchone()
        if not dest:
            raise HTTPException(status_code=404, detail=f"Conta destino {data.to_account_number} não encontrada.")
        to_account_id = dest["id"]

    try:
        res = execute_internal_transfer(
            from_account_id=data.from_account_id,
            to_account_id=to_account_id,
            amount_minor=amount_minor,
            idempotency_key=data.idempotency_key,
            description=data.description
        )
        return res
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/transfers/iban")
def transfer_iban(
    data: IbanTransferCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    
    # Identificar moeda da conta de origem
    with get_connection() as conn:
        acc = conn.execute("SELECT currency FROM accounts WHERE id = ?", (data.from_account_id,)).fetchone()
        if not acc:
            raise HTTPException(status_code=404, detail="Conta de origem não encontrada.")
        source_currency = acc["currency"]

    try:
        res = PayoutProvider.transferir_para_iban(
            from_account_id=data.from_account_id,
            to_iban=data.to_iban,
            beneficiary_name=data.beneficiary_name,
            amount_minor=amount_minor,
            source_currency=source_currency,
            dest_currency=data.dest_currency,
            idempotency_key=data.idempotency_key
        )
        return res
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- VALIDAÇÃO DE IBAN -----------------

@app.get("/api/iban/validate")
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

# ----------------- CÂMBIO & COTAÇÃO -----------------

@app.post("/api/fx/quote")
def get_fx_quote(data: FxQuoteRequest):
    amount_minor = int(round(data.amount * 100))
    try:
        quote = FXProvider.get_quote(data.from_currency, data.to_currency, amount_minor)
        return quote
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- HISTÓRICO & EXTRATO -----------------

@app.get("/api/transactions")
def get_transactions(current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT l.id, l.transaction_id, l.amount_minor, l.currency, l.created_at,
                   t.type, t.status, t.description, a.account_number
            FROM ledger_entries l
            JOIN transactions t ON l.transaction_id = t.id
            JOIN accounts a ON l.account_id = a.id
            WHERE a.user_id = ?
            ORDER BY l.created_at DESC
            LIMIT 50
            """,
            (current_user["id"],)
        ).fetchall()

        return [
            {
                "id": r["id"],
                "transaction_id": r["transaction_id"],
                "amount_minor": r["amount_minor"],
                "amount_decimal": r["amount_minor"] / 100.0,
                "currency": r["currency"],
                "type": r["type"],
                "status": r["status"],
                "description": r["description"],
                "account_number": r["account_number"],
                "created_at": r["created_at"]
            }
            for r in rows
        ]

# ----------------- ASSISTENTE DE IA (META MODEL API) -----------------

@app.post("/api/ai/chat")
def ai_chat(data: AIChatRequest):
    reply = BankaoAssistant.chat(data.message, data.history)
    return {
        "reply": reply,
        "model": settings.MODEL_NAME,
        "provider": "Meta Model API / Muse Spark"
    }

@app.post("/api/ai/explain-transfer")
def ai_explain_transfer(data: AIExplainTransferRequest):
    explanation = BankaoAssistant.explain_transfer(
        source_amount=data.source_amount,
        source_currency=data.source_currency,
        dest_amount=data.dest_amount,
        dest_currency=data.dest_currency,
        fx_rate=data.fx_rate,
        fee=data.fee,
        dest_iban=data.dest_iban,
        beneficiary_name=data.beneficiary_name
    )
    return {
        "explanation": explanation,
        "model": settings.MODEL_NAME
    }

@app.get("/api/ai/analyze-risk")
def ai_analyze_risk(
    amount: float,
    currency: str,
    tx_type: str,
    current_user: dict = Depends(get_current_user)
):
    analysis = BankaoAssistant.analyze_risk(
        amount=amount,
        currency=currency,
        tx_type=tx_type,
        user_kyc_status=current_user.get("kyc_status", "verificado")
    )
    return analysis

# ----------------- ARQUIVOS ESTÁTICOS FRONTEND -----------------

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_dir, "index.html"))
