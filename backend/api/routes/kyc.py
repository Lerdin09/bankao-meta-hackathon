"""
Rotas — KYC: Verificação de identidade com IA.
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
