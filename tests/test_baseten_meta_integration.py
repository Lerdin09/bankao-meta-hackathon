"""
Testes de Integração Baseten & Meta (Muse Spark Open 1026).
Garante compatibilidade total com o modelo oficial do Meta Global AI Developer Hackathon.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.core.config import Settings
from backend.ai.client import (
    extract_reasoning_and_content,
    get_active_provider_info,
    build_multimodal_message,
)
from backend.ai.vision import analyze_financial_document

client = TestClient(app)


def test_baseten_settings_resolution():
    """Valida resolução automática para o provedor Baseten e modelo do Hackathon."""
    s = Settings()
    s.AI_PROVIDER = "auto"
    s.BASETEN_API_KEY = "test_baseten_key_123"
    assert s.active_ai_provider == "baseten"
    assert s.active_model_name == "meta-models/muse-spark-open-1026"
    assert s.active_base_url == "https://inference.baseten.co/v1"
    assert s.active_api_key == "test_baseten_key_123"
    assert s.is_ai_configured is True


def test_muse_spark_reasoning_extraction_native():
    """Valida extração de reasoning_content nativo emitido pelo Muse Spark Open no Baseten."""
    mock_choice = MagicMock()
    mock_choice.message.content = "O seu saldo em Kwanza é de 1.250.000 Kz."
    mock_choice.message.reasoning_content = (
        "1. Analisar saldo do utilizador em Kwanzas.\n"
        "2. Verificar se há contas em moeda estrangeira.\n"
        "3. Responder de forma amigável e direta em português."
    )

    extracted = extract_reasoning_and_content(mock_choice)
    assert extracted["clean_content"] == "O seu saldo em Kwanza é de 1.250.000 Kz."
    assert "Analisar saldo" in extracted["reasoning"]


def test_muse_spark_reasoning_extraction_think_tags():
    """Valida separação de tags <think>...</think> para respostas limpas ao utilizador."""
    mock_choice = MagicMock()
    mock_choice.message.content = (
        "<think>\nO cliente quer enviar 50.000 Kz para o Carlos via IBAN AO060044.\n"
        "Vou preparar o cartão de transferência sem executar.\n</think>\n"
        "Preparei a transferência de **50.000 Kz** para o Carlos. Por favor, reveja e confirme os dados no ecrã."
    )
    mock_choice.message.reasoning_content = None

    extracted = extract_reasoning_and_content(mock_choice)
    assert "<think>" not in extracted["clean_content"]
    assert "</think>" not in extracted["clean_content"]
    assert "Preparei a transferência" in extracted["clean_content"]
    assert "Carlos via IBAN" in extracted["reasoning"]


def test_provider_status_endpoint():
    """Valida endpoint /api/ai/provider-status."""
    r = client.get("/api/ai/provider-status")
    assert r.status_code == 200
    data = r.json()
    assert "provider" in data
    assert "model" in data
    assert "base_url" in data
    assert "features" in data
    assert data["features"]["reasoning"] is True
    assert data["features"]["tool_calling"] is True
    assert data["features"]["vision"] is True


def test_multimodal_message_builder():
    """Valida formatação correta de mensagens visuais para o Muse Spark Open Vision."""
    raw_bytes = b"fake_jpeg_image_content"
    messages = build_multimodal_message("Extrai o total desta fatura", raw_bytes, "image/jpeg")
    assert len(messages) == 1
    content = messages[0]["content"]
    assert len(content) == 2
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_vision_analyze_financial_document_mock():
    """Valida análise visual de comprovativo com sugestão de ação BankAO."""
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = """
    ```json
    {
      "document_type": "recibo_compra",
      "merchant_or_entity": "Kero Hipermercado",
      "amount": 28450.0,
      "currency": "AOA",
      "date": "2026-11-04",
      "category": "Alimentação",
      "summary": "Compra de supermercado de 28.450 Kz no Kero.",
      "suggested_action": "EXPENSE_REGISTER"
    }
    ```
    """
    mock_choice.message.reasoning_content = "Identifiquei recibo do Kero com total de 28450 AOA."
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("backend.ai.vision.get_meta_client", return_value=mock_client):
        res = analyze_financial_document(b"sample_receipt_image", "image/png")
        assert res["ok"] is True
        assert res["document"]["merchant_or_entity"] == "Kero Hipermercado"
        assert res["document"]["amount"] == 28450.0
        assert res["action"] is not None
        assert res["action"]["type"] == "EXPENSE_REGISTERED"
        assert res["action"]["category"] == "Alimentação"
        assert "Identifiquei recibo" in res["reasoning"]

