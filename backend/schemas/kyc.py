"""
Modelos Pydantic — KYC — verificação de identidade com IA.
"""
from typing import Optional
from pydantic import BaseModel, Field


class KYCExtractRequest(BaseModel):
    doc_type: str = Field(..., description="'bilhete' ou 'passaporte'")
    foto_frente: str = Field(..., description="Imagem base64 da frente ou página de dados")
    foto_verso: str = Field(..., description="Imagem base64 do verso ou página de assinatura")


class KYCConfirmRequest(BaseModel):
    nome_completo: str
    primeiro_nome: str
    ultimo_nome: str
    nome_pai: Optional[str] = ""
    nome_mae: Optional[str] = ""
    doc_tipo: str = "bilhete"
    doc_numero: str
    morada: Optional[str] = ""
    data_emissao: Optional[str] = ""
