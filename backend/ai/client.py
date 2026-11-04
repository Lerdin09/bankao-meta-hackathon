"""
Cliente Unificado de IA: Baseten & Meta Model API (Muse Spark Open).
Compatível com a API OpenAI (base_url + api_key).

Suporta:
- Baseten como plataforma de inferência de alta performance para o Meta Global AI Developer Hackathon.
- Modelo oficial do Hackathon: meta-models/muse-spark-open-1026 (2M tokens/min).
- Extração avançada de Raciocínio (Chain-of-Thought / reasoning_content / <think>).
- Suporte a Tool Calling / Function Calling.
- Suporte a Visão Multimodal (análise de comprovativos e faturas).
- Retentativas com backoff exponencial e fallback transparente.
"""
import base64
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import OpenAI

from backend.core.config import settings

logger = logging.getLogger("bankao.ai_client")

# Cache de instâncias do cliente para reuso de connection pool
_cached_client: Optional[OpenAI] = None
_cached_key: Optional[str] = None
_cached_url: Optional[str] = None


def get_meta_client() -> Optional[OpenAI]:
    """
    Retorna o cliente OpenAI configurado para o provedor ativo (Baseten ou Meta).
    Retorna None quando não existe chave configurada (ativando fallback local).
    """
    global _cached_client, _cached_key, _cached_url

    if not settings.is_ai_configured:
        return None

    api_key = settings.active_api_key
    base_url = settings.active_base_url

    if _cached_client is not None and _cached_key == api_key and _cached_url == base_url:
        return _cached_client

    try:
        # Timeout customizado com httpx client
        http_client = httpx.Client(
            timeout=httpx.Timeout(settings.AI_REQUEST_TIMEOUT, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
        )
        _cached_client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
        )
        _cached_key = api_key
        _cached_url = base_url
        logger.info(
            "Cliente de IA inicializado com sucesso [Provider: %s, Model: %s, URL: %s]",
            settings.active_ai_provider,
            settings.active_model_name,
            base_url,
        )
        return _cached_client
    except Exception as e:
        logger.error("Erro ao criar cliente OpenAI/Baseten: %s", e)
        return None


def get_baseten_client() -> Optional[OpenAI]:
    """Retorna explicitamente o cliente Baseten se configurado."""
    return get_meta_client()


def get_active_provider_info() -> Dict[str, Any]:
    """Retorna metadados detalhados do provedor e modelo de IA ativo."""
    provider = settings.active_ai_provider
    is_configured = settings.is_ai_configured
    key = settings.active_api_key
    masked_key = (key[:6] + "..." + key[-4:]) if len(key) > 10 else ("***" if key else "")

    provider_label = "Baseten (Meta Muse Spark Open)" if provider == "baseten" else (
        "Meta Direct API" if provider == "meta" else "Modo Local / Offline"
    )

    return {
        "provider": provider,
        "provider_label": provider_label,
        "model": settings.active_model_name,
        "base_url": settings.active_base_url,
        "is_configured": is_configured,
        "api_key_masked": masked_key,
        "features": {
            "reasoning": True,
            "tool_calling": True,
            "vision": True,
            "audio": True,
            "multilingual_pt": True,
        },
        "limits": "2M tokens/minuto (Baseten Hackathon Pool)" if provider == "baseten" else "Standard",
        "credits": "$100 Hackathon Grant" if provider == "baseten" else "N/A",
    }


# ─── Extrator de Raciocínio (Chain-of-Thought) ────────────────────────────────

RE_THINK_TAGS = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
RE_REASONING_TAGS = re.compile(r"\[REASONING\](.*?)\[/REASONING\]", re.DOTALL | re.IGNORECASE)


def extract_reasoning_and_content(message_or_choice: Any) -> Dict[str, str]:
    """
    Muse Spark Open sempre raciocina.
    Esta função extrai com precisão cirúrgica:
    - 'reasoning': O processo de pensamento (chain-of-thought) do modelo.
    - 'clean_content': A resposta limpa, polida e pronta para o utilizador.
    """
    raw_content = ""
    reasoning_parts: List[str] = []

    # 1. Campo nativo 'reasoning_content' da API Baseten / vLLM
    if hasattr(message_or_choice, "message"):
        msg = message_or_choice.message
    else:
        msg = message_or_choice

    native_reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    if native_reasoning and isinstance(native_reasoning, str):
        reasoning_parts.append(native_reasoning.strip())

    raw_content = getattr(msg, "content", None) or ""

    # 2. Tags <think>...</think> presentes no conteúdo
    clean_content = raw_content
    for match in RE_THINK_TAGS.finditer(raw_content):
        reasoning_parts.append(match.group(1).strip())
    clean_content = RE_THINK_TAGS.sub("", clean_content).strip()

    # 3. Tags [REASONING]...[/REASONING]
    for match in RE_REASONING_TAGS.finditer(clean_content):
        reasoning_parts.append(match.group(1).strip())
    clean_content = RE_REASONING_TAGS.sub("", clean_content).strip()

    # Se o conteúdo limpo ficou vazio mas havia raciocínio, usa o raciocínio como resposta
    if not clean_content and reasoning_parts:
        clean_content = reasoning_parts[-1]

    full_reasoning = "\n\n".join(p for p in reasoning_parts if p)

    return {
        "raw_content": raw_content,
        "clean_content": clean_content,
        "reasoning": full_reasoning,
    }


# ─── Execução com Resiliência e Retentativas ──────────────────────────────────

def safe_chat_completion(
    client: OpenAI,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = "auto",
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    max_retries: int = 2,
) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """
    Executa chat.completions com retentativa exponencial para erros transitórios (429, 502, 503).
    Retorna (response, metrics_dict).
    """
    model = settings.active_model_name
    tokens = max_tokens or settings.AI_MAX_TOKENS
    temp = temperature if temperature is not None else settings.AI_TEMPERATURE

    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": tokens,
        "temperature": temp,
        "timeout": settings.AI_REQUEST_TIMEOUT,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    last_error = None
    start_time = time.perf_counter()

    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.perf_counter()
            response = client.chat.completions.create(**kwargs)
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)

            usage = getattr(response, "usage", None)
            metrics = {
                "duration_ms": duration_ms,
                "model": model,
                "provider": settings.active_ai_provider,
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
            }
            logger.debug(
                "Chamada IA bem sucedida (%s ms, %s tokens)",
                duration_ms,
                metrics["total_tokens"],
            )
            return response, metrics
        except Exception as e:
            last_error = e
            err_msg = str(e)
            logger.warning("Falha na chamada IA (tentativa %s/%s): %s", attempt, max_retries, err_msg)
            # Se for erro 429 ou 5xx transitório, aguarda backoff
            if attempt < max_retries and any(code in err_msg for code in ("429", "502", "503", "504", "timeout")):
                time.sleep(1.0 * attempt)
            else:
                break

    total_duration = round((time.perf_counter() - start_time) * 1000, 1)
    logger.error("Todas as tentativas falharam após %s ms: %s", total_duration, last_error)
    return None, {"error": str(last_error), "duration_ms": total_duration}


# ─── Utilitários Multimodais (Vision & Audio) ──────────────────────────────────

def build_multimodal_message(
    text_prompt: str,
    image_bytes_or_b64: Any,
    mime_type: str = "image/jpeg",
) -> List[Dict[str, Any]]:
    """
    Formata mensagem multimodal para o Muse Spark Open via Baseten Vision API.
    """
    if isinstance(image_bytes_or_b64, bytes):
        b64_str = base64.b64encode(image_bytes_or_b64).decode("utf-8")
    else:
        b64_str = str(image_bytes_or_b64)
        if b64_str.startswith("data:"):
            b64_str = b64_str.split(",", 1)[-1]

    data_url = f"data:{mime_type};base64,{b64_str}"

    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]


def test_ai_connection() -> Dict[str, Any]:
    """
    Testa a conectividade com o modelo Baseten / Meta enviando um prompt rápido.
    Retorna métricas de latência e resposta.
    """
    client = get_meta_client()
    if not client:
        return {
            "ok": False,
            "status": "not_configured",
            "message": "Nenhuma chave de API configurada no .env (configure BASETEN_API_KEY ou MODEL_API_KEY).",
            "provider_info": get_active_provider_info(),
        }

    try:
        t0 = time.perf_counter()
        response = client.chat.completions.create(
            model=settings.active_model_name,
            messages=[{"role": "user", "content": "Olá, confirma que estás operacional respondendo 'OK' em 1 palavra."}],
            max_tokens=60,
            temperature=0.1,
            timeout=15,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        parsed = extract_reasoning_and_content(response.choices[0])

        return {
            "ok": True,
            "status": "operational",
            "latency_ms": latency_ms,
            "reply": parsed["clean_content"],
            "has_reasoning": bool(parsed["reasoning"]),
            "provider_info": get_active_provider_info(),
        }
    except Exception as e:
        return {
            "ok": False,
            "status": "error",
            "error": str(e),
            "provider_info": get_active_provider_info(),
        }
