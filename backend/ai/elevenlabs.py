"""
Serviço de Integração ElevenLabs / ElevenAgents para o BankAO.
Fornece:
1. Obtenção segura de Signed URL para WebSockets de voz (evita expor a ELEVENLABS_API_KEY no browser).
2. Verificação de credenciais e parâmetros de voz.
3. Tratamento de webhook tools invocadas pelo ElevenAgents.
"""
import logging
from typing import Any, Dict, Optional
import httpx

from backend.core.config import settings

logger = logging.getLogger("bankao.ai.elevenlabs")

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"


def get_signed_url_for_agent(agent_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtém conexão para o agente ElevenLabs.
    1. Tenta obter Signed URL segura via xi-api-key (se a chave tiver a permissão convai_write).
    2. Se a chave não tiver convai_write ou se o agente não tiver autenticação restrita ativa,
       devolve o agent_id diretamente para conexão pública/direta via SDK.
    """
    api_key = settings.ELEVENLABS_API_KEY
    target_agent_id = agent_id or settings.ELEVENLABS_AGENT_ID

    if not target_agent_id:
        return {
            "ok": False,
            "error": "ELEVENLABS_AGENT_ID não configurado no servidor (.env).",
            "signed_url": None,
            "agent_id": None
        }

    # Se não houver API key mas houver agent_id, permite conexão direta pelo agent_id
    if not api_key:
        return {
            "ok": True,
            "signed_url": None,
            "agent_id": target_agent_id,
            "use_direct_agent": True
        }

    url = f"{ELEVENLABS_API_BASE}/v1/convai/conversation/get-signed-url"
    headers = {
        "xi-api-key": api_key,
        "Accept": "application/json"
    }
    params = {
        "agent_id": target_agent_id
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "ok": True,
                    "signed_url": data.get("signed_url"),
                    "agent_id": target_agent_id,
                    "use_direct_agent": False
                }
            else:
                logger.info(
                    "Signed URL não emitida (HTTP %s). Usando inicialização direta por Agent ID.",
                    resp.status_code
                )
                return {
                    "ok": True,
                    "signed_url": None,
                    "agent_id": target_agent_id,
                    "use_direct_agent": True,
                    "note": "Conexão direta por Agent ID autorizada."
                }
    except Exception as exc:
        logger.warning("Falha de rede ao contactar ElevenLabs para signed URL: %s", exc)
        return {
            "ok": True,
            "signed_url": None,
            "agent_id": target_agent_id,
            "use_direct_agent": True
        }


def get_eleven_status() -> Dict[str, Any]:
    """Retorna o estado da configuração do ElevenLabs no BankAO."""
    return {
        "is_configured": bool(settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_AGENT_ID),
        "has_api_key": bool(settings.ELEVENLABS_API_KEY),
        "has_agent_id": bool(settings.ELEVENLABS_AGENT_ID),
        "agent_id": settings.ELEVENLABS_AGENT_ID or None,
        "custom_llm_model": settings.active_model_name,
        "custom_llm_provider": settings.active_ai_provider,
        "auth_secret_configured": bool(settings.ELEVENLABS_CUSTOM_LLM_SECRET)
    }
