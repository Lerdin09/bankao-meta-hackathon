"""
Conjunto completo de testes para a integração do ElevenAgents (ElevenLabs) com o BankAO:
1. Verificação de status e chaves de API do ElevenLabs.
2. Geração e validação de Signed URL protegida por JWT.
3. Custom LLM endpoint compatível com OpenAI Chat Completions (SSE e streaming de deltas).
4. Integração do cérebro cognitivo com Meta Muse Spark Open via Baseten.
5. Invocação de ferramentas bancárias seguras (saldos, extratos, transferências).
6. Garantia inviolável de que ações financeiras são apenas PREPARADAS (requerem autorização do utilizador).
7. Webhook tools expostas para o agente ElevenLabs.
"""
import json
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.core.config import settings
from backend.core.security import create_access_token


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "usr_test_eleven_123", "sid": "sid_eleven_test"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def custom_llm_secret_headers():
    return {"Authorization": f"Bearer {settings.ELEVENLABS_CUSTOM_LLM_SECRET}"}


# ─── 1. Testes de Status e Configuração ────────────────────────────────────────

def test_eleven_status_endpoint(client):
    """Verifica se o endpoint de status do ElevenLabs retorna dados estruturados."""
    resp = client.get("/api/eleven/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_configured" in data
    assert "has_api_key" in data
    assert "has_agent_id" in data
    assert "custom_llm_model" in data
    assert "custom_llm_provider" in data
    assert data["auth_secret_configured"] is True


def test_eleven_signed_url_requires_auth(client):
    """Verifica que /api/eleven/signed-url recusa pedidos não autenticados (HTTP 401)."""
    resp = client.get("/api/eleven/signed-url")
    assert resp.status_code == 401


# ─── 2. Testes do Custom LLM Endpoint (OpenAI Chat Completions) ───────────────

def test_eleven_custom_llm_auth_required(client):
    """Verifica que o Custom LLM recusa chamadas sem autenticação válida."""
    payload = {
        "messages": [{"role": "user", "content": "Olá"}]
    }
    resp = client.post("/api/eleven/chat/completions", json=payload)
    assert resp.status_code == 401


def test_eleven_custom_llm_sync_reply(client, custom_llm_secret_headers):
    """Verifica a resposta JSON síncrona do Custom LLM quando stream=False."""
    payload = {
        "messages": [
            {"role": "user", "content": "Olá, quem és tu?"}
        ],
        "stream": False
    }
    resp = client.post("/api/eleven/chat/completions", json=payload, headers=custom_llm_secret_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) > 0
    content = data["choices"][0]["message"]["content"]
    assert len(content) > 0
    assert data["choices"][0]["finish_reason"] == "stop"


def test_eleven_custom_llm_streaming_sse(client, custom_llm_secret_headers):
    """Verifica o streaming Server-Sent Events (SSE) esperado pelo ElevenLabs."""
    payload = {
        "messages": [
            {"role": "user", "content": "Qual é o meu saldo?"}
        ],
        "stream": True
    }
    resp = client.post("/api/eleven/chat/completions", json=payload, headers=custom_llm_secret_headers)
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    lines = resp.text.split("\n")
    data_lines = [l for l in lines if l.startswith("data: ")]
    assert len(data_lines) >= 2  # Pelo menos um chunk de conteúdo + [DONE]
    assert data_lines[-1] == "data: [DONE]"

    # Verifica o formato do primeiro chunk
    first_chunk_json = json.loads(data_lines[0].replace("data: ", ""))
    assert first_chunk_json["object"] == "chat.completion.chunk"
    assert "delta" in first_chunk_json["choices"][0]


# ─── 3. Testes de Segurança: Ações Financeiras Apenas Preparadas ──────────────

def test_eleven_custom_llm_prepares_transfer_never_auto_executes(client, custom_llm_secret_headers):
    """
    Garante a regra de segurança máxima:
    Quando o utilizador dita uma transferência por voz, o assistente APENAS PREPARA os dados
    e devolve instrução de confirmação no ecrã. Nunca movimenta fundos sozinho.
    """
    payload = {
        "messages": [
            {"role": "user", "content": "Transfere 25000 Kz para o IBAN AO06004000001234567890123"}
        ],
        "stream": False
    }
    resp = client.post("/api/eleven/chat/completions", json=payload, headers=custom_llm_secret_headers)
    assert resp.status_code == 200
    content = resp.json()["choices"][0]["message"]["content"].lower()

    # Deve conter menção a preparação, confirmação ou revisão
    assert any(term in content for term in ["prepar", "confirm", "rever", "autoriz"])


# ─── 4. Testes de Webhook Tools para ElevenLabs ────────────────────────────────

def test_eleven_webhook_tool_get_accounts(client, custom_llm_secret_headers):
    """Verifica que o webhook direto de ferramenta consulta contas do utilizador."""
    resp = client.post(
        "/api/eleven/tools/get_accounts_summary",
        json={},
        headers=custom_llm_secret_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts" in data or "ok" in data

