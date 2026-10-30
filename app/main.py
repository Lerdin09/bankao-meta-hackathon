"""
Aplicação Principal FastAPI — BankAO (Meta Global AI Developer Hackathon).
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
from app.ai.kyc import DocumentKYCExtractor
from app.schemas import (
    UserRegister, UserLogin, TokenResponse,
    KYCExtractRequest, KYCConfirmRequest,
    DepositReferenciaCreate, DepositExpressCreate, DepositSimulatePayment,
    InternalTransferCreate, IbanTransferCreate, FxQuoteRequest,
    AIChatRequest, AIExplainTransferRequest
)

# Inicializar Base de Dados e tabelas do livro-razão
init_db()

app = FastAPI(
    title="BankAO API",
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

        # Criar automaticamente carteira em Kwanza (AOA), Euro (EUR) e Dólar (USD)
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
        iban_usd = gerar_iban_ficticio("AO")
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

@app.post("/api/auth/login", response_model=TokenResponse)
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

@app.get("/api/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user

# ----------------- KYC / VERIFICAÇÃO DE IDENTIDADE COM IA -----------------

@app.post("/api/kyc/extract")
def kyc_extract(
    data: KYCExtractRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submete fotos de documento à IA (Meta Model API / Muse Spark)
    e extrai estruturadamente todos os dados cadastrais solicitados.
    """
    try:
        extracted = DocumentKYCExtractor.extract_document_data(
            doc_type=data.doc_type,
            foto_frente=data.foto_frente,
            foto_verso=data.foto_verso
        )
        return {
            "success": True,
            "extracted": extracted
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na extração de dados do documento: {str(e)}")

@app.post("/api/kyc/confirm")
def kyc_confirm(
    data: KYCConfirmRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Salva os dados de KYC validados no perfil do utilizador,
    atualiza o estado para 'verificado' e credita o bónus inicial de sandbox.
    """
    user_id = current_user["id"]
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET nome = ?,
                primeiro_nome = ?,
                ultimo_nome = ?,
                nome_pai = ?,
                nome_mae = ?,
                doc_tipo = ?,
                doc_numero = ?,
                morada = ?,
                data_emissao = ?,
                kyc_status = 'verificado'
            WHERE id = ?
            """,
            (
                data.nome_completo,
                data.primeiro_nome,
                data.ultimo_nome,
                data.nome_pai or "",
                data.nome_mae or "",
                data.doc_tipo,
                data.doc_numero,
                data.morada or "",
                data.data_emissao or "",
                user_id
            )
        )

        # Buscar contas do utilizador para creditar bónus de boas-vindas sandbox se ainda não creditado
        bonus_config = [
            ("AOA", 10000000, "Bónus de Boas-Vindas BankAO (100.000 Kz Sandbox)"),
            ("USD", 1000000, "Bónus de Boas-Vindas BankAO ($10.000 Sandbox)"),
            ("EUR", 1000000, "Bónus de Boas-Vindas BankAO (10.000 € Sandbox)")
        ]
        for b_curr, b_minor, b_desc in bonus_config:
            acc_cur = conn.execute("SELECT id FROM accounts WHERE user_id = ? AND currency = ?", (user_id, b_curr)).fetchone()
            if acc_cur:
                has_bonus = conn.execute(
                    """
                    SELECT id FROM transactions
                    WHERE description LIKE '%Bónus%'
                      AND id IN (SELECT transaction_id FROM ledger_entries WHERE account_id = ?)
                    """,
                    (acc_cur["id"],)
                ).fetchone()
                if not has_bonus:
                    tx_id = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO transactions (id, type, status, description) VALUES (?, 'deposit', 'completed', ?)",
                        (tx_id, b_desc)
                    )
                    conn.execute(
                        "INSERT INTO ledger_entries (transaction_id, account_id, amount_minor, currency) VALUES (?, ?, ?, ?)",
                        (tx_id, acc_cur["id"], b_minor, b_curr)
                    )

        user = conn.execute(
            """
            SELECT id, nome, primeiro_nome, ultimo_nome, email, telefone, kyc_status,
                   nome_pai, nome_mae, doc_tipo, doc_numero, morada, data_emissao
            FROM users WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

    return {
        "success": True,
        "message": "Identidade verificada com sucesso! A sua carteira BankAO está ativa.",
        "user": dict(user)
    }

@app.get("/api/kyc/samples/{doc_type}")
def get_sample_document(doc_type: str):
    """
    Retorna as imagens de teste pré-carregadas em base64 para facilitar demonstrações e testes rápidos.
    """
    import base64
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "samples"))
    if doc_type == "passaporte":
        frente_path = os.path.join(base_dir, "passaporte_frente.png")
        verso_path = os.path.join(base_dir, "passaporte_verso.png")
    else:
        frente_path = os.path.join(base_dir, "bi_frente.png")
        verso_path = os.path.join(base_dir, "bi_verso.png")

    if not os.path.exists(frente_path) or not os.path.exists(verso_path):
        raise HTTPException(status_code=404, detail="Amostras não encontradas.")

    with open(frente_path, "rb") as f1, open(verso_path, "rb") as f2:
        frente_b64 = "data:image/png;base64," + base64.b64encode(f1.read()).decode("utf-8")
        verso_b64 = "data:image/png;base64," + base64.b64encode(f2.read()).decode("utf-8")

    return {
        "doc_type": doc_type,
        "foto_frente": frente_b64,
        "foto_verso": verso_b64
    }

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

# ----------------- TRANSFERÊNCIAS & DESTINATÁRIOS -----------------

@app.get("/api/users/lookup")
def lookup_user(email: str, current_user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        u = conn.execute(
            "SELECT id, nome, primeiro_nome, ultimo_nome, email FROM users WHERE lower(email) = lower(?)",
            (email.strip(),)
        ).fetchone()
        if not u:
            return {"found": False}
        nome_completo = u["nome"]
        if not nome_completo or nome_completo == "Novo Utilizador":
            nome_completo = f"{u['primeiro_nome'] or ''} {u['ultimo_nome'] or ''}".strip() or u["email"]
        return {
            "found": True,
            "id": u["id"],
            "nome": nome_completo,
            "email": u["email"]
        }

@app.post("/api/transfers/internal")
def transfer_internal(
    data: InternalTransferCreate,
    current_user: dict = Depends(get_current_user)
):
    amount_minor = int(round(data.amount * 100))
    if amount_minor <= 0:
        raise HTTPException(status_code=400, detail="O montante deve ser estritamente maior que zero.")

    # Descobrir a conta de destino pelo e-mail ou número de conta
    with get_connection() as conn:
        dest = None
        beneficiary_name = "Cliente BankAO"

        if data.to_email:
            dest_user = conn.execute(
                "SELECT id, nome, primeiro_nome, ultimo_nome, email FROM users WHERE lower(email) = lower(?)",
                (data.to_email.strip(),)
            ).fetchone()
            if not dest_user:
                raise HTTPException(status_code=404, detail=f"Cliente com e-mail '{data.to_email}' não encontrado.")
            
            nome_cand = dest_user["nome"]
            if not nome_cand or nome_cand == "Novo Utilizador":
                nome_cand = f"{dest_user['primeiro_nome'] or ''} {dest_user['ultimo_nome'] or ''}".strip() or dest_user["email"]
            beneficiary_name = nome_cand

            from_acc = conn.execute("SELECT currency FROM accounts WHERE id = ?", (data.from_account_id,)).fetchone()
            curr = from_acc["currency"] if from_acc else "AOA"
            dest = conn.execute(
                "SELECT id, account_number FROM accounts WHERE user_id = ? AND currency = ? AND status = 'active'",
                (dest_user["id"], curr)
            ).fetchone()
            if not dest:
                dest = conn.execute(
                    "SELECT id, account_number FROM accounts WHERE user_id = ? AND status = 'active' LIMIT 1",
                    (dest_user["id"],)
                ).fetchone()

        elif data.to_account_number:
            dest = conn.execute(
                "SELECT a.id, a.account_number, u.nome, u.primeiro_nome, u.ultimo_nome FROM accounts a JOIN users u ON a.user_id = u.id WHERE a.account_number = ?",
                (data.to_account_number.strip(),)
            ).fetchone()
            if dest:
                beneficiary_name = dest["nome"] or f"{dest['primeiro_nome'] or ''} {dest['ultimo_nome'] or ''}".strip() or "Cliente BankAO"
            else:
                dest_direct = conn.execute("SELECT id FROM accounts WHERE account_number = ?", (data.to_account_number.strip(),)).fetchone()
                if dest_direct:
                    dest = dest_direct

        if not dest:
            raise HTTPException(status_code=404, detail="Conta ou e-mail de destino não encontrado.")
        to_account_id = dest["id"]

    # Taxa de 1% para transferência entre contas
    fee_minor = int(round(amount_minor * 0.01))
    dest_amount_minor = max(0, amount_minor - fee_minor)

    try:
        res = execute_internal_transfer(
            from_account_id=data.from_account_id,
            to_account_id=to_account_id,
            amount_minor=amount_minor,
            fee_minor=fee_minor,
            idempotency_key=data.idempotency_key,
            description=data.description,
            beneficiary_name=beneficiary_name
        )
        res["beneficiary_name"] = beneficiary_name
        res["source_amount_decimal"] = amount_minor / 100.0
        res["dest_amount_decimal"] = dest_amount_minor / 100.0
        res["fee_decimal"] = fee_minor / 100.0
        res["fee_percentage"] = 1.0
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
        quote = FXProvider.get_quote(data.from_currency, data.to_currency, amount_minor, custom_fee_pct=0.025)
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
            LIMIT 500
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
    res = BankaoAssistant.chat_with_action(data.message, data.history)
    return {
        "reply": res["reply"],
        "action": res.get("action"),
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
