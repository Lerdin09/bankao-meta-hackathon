"""
Rotas — KYC: Verificação de identidade com IA e documentos de demonstração.
"""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException

from backend.ai.kyc import DocumentKYCExtractor
from backend.core.config import settings
from backend.core.security import get_current_user
from backend.database import get_connection
from backend.schemas import KYCConfirmRequest, KYCExtractRequest

router = APIRouter(prefix="/api/kyc", tags=["KYC"])


@router.post("/extract")
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


@router.post("/confirm")
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


@router.get("/samples/{doc_type}")
def get_sample_document(doc_type: str):
    """
    Retorna as imagens de teste pré-carregadas em base64 para facilitar demonstrações e testes rápidos.
    """
    import base64
    base_dir = settings.SAMPLES_DIR
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
