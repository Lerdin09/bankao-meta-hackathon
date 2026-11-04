"""
Router do Custom LLM e Ferramentas para ElevenAgents (ElevenLabs Conversational AI).
Compatível com OpenAI Chat Completions API (/v1/chat/completions) e SSE streaming.

Recebe as mensagens transcritas por voz do ElevenLabs, processa através da
arquitetura de agentes do BankAO movida a Meta Muse Spark Open via Baseten,
executa as ferramentas bancárias de forma segura, garante que ações financeiras
são apenas PREPARADAS (requerem confirmação e autorização do utilizador),
e transmite o áudio falado de forma ultra-rápida.
"""
import asyncio
import json
import logging
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request, Depends, status
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from backend.ai.agent import run_agent
from backend.ai.client import get_meta_client
from backend.ai.elevenlabs import get_signed_url_for_agent, get_eleven_status
from backend.ai.tools.registry import execute_tool, BANKAO_TOOLS_DEFINITIONS
from backend.core.config import settings
from backend.core.security import get_current_user
from backend.database import get_connection

logger = logging.getLogger("bankao.eleven_custom_llm")

router = APIRouter(prefix="/api/eleven", tags=["ElevenLabs Voice & Custom LLM"])


def verify_eleven_custom_llm_auth(authorization: Optional[str] = Header(None)) -> bool:
    """
    Verifica a autenticação do ElevenLabs Custom LLM.
    Aceita Bearer com o segredo configurado (ELEVENLABS_CUSTOM_LLM_SECRET)
    ou token JWT caso uma sessão de utilizador seja injetada.
    Se ELEVENLABS_CUSTOM_LLM_SECRET não estiver preenchido com valor restrito,
    permite conexões locais/desenvolvimento mas regista alerta.
    """
    secret = settings.ELEVENLABS_CUSTOM_LLM_SECRET
    if not secret:
        return True

    if not authorization:
        # Se houver segredo obrigatório mas sem header
        logger.warning("Tentativa de acesso ao Custom LLM ElevenLabs sem header Authorization.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória para o Custom LLM ElevenLabs."
        )

    token = authorization.replace("Bearer ", "").strip()
    if token == secret:
        return True

    # Também permite tokens JWT válidos de utilizador BankAO
    from jose import jwt, JWTError
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("sub"):
            return True
    except JWTError:
        pass

    logger.warning("Token inválido recebido no Custom LLM ElevenLabs.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas para o Custom LLM ElevenLabs."
    )


def _resolve_user_id_from_messages_or_db(messages: List[Dict[str, Any]], request_headers: Dict[str, Any]) -> str:
    """
    Localiza o utilizador associado à chamada.
    1. Verifica se foi passado um header X-Bankao-User-Id ou token.
    2. Verifica o utilizador padrão/ativo na base de dados para a demonstração bancária.
    """
    # 1. Header direto
    uid = request_headers.get("x-bankao-user-id")
    if uid:
        return str(uid).strip()

    # 2. Utilizador padrão (primeiro utilizador ativo da BD)
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM users ORDER BY created_at ASC LIMIT 1").fetchone()
            if row and row["id"]:
                return str(row["id"])
    except Exception as e:
        logger.warning("Erro ao resolver utilizador padrão da BD: %s", e)

    return "usr_default_demo"


# ─── Endpoints de Estado e Conexão de Voz ──────────────────────────────────────

@router.get("/status")
def api_eleven_status():
    """Retorna o estado da integração ElevenLabs / ElevenAgents."""
    return get_eleven_status()


@router.get("/signed-url")
def api_eleven_signed_url(current_user: dict = Depends(get_current_user)):
    """
    Gera credenciais seguras para o cliente web/mobile iniciar a chamada com o agente ElevenLabs.
    Se a chave tiver permissão de assinatura, emite Signed URL; caso contrário, autoriza por Agent ID.
    """
    res = get_signed_url_for_agent()
    if not res.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=res.get("error", "Não foi possível obter conexão com a ElevenLabs.")
        )
    return {
        "ok": True,
        "signed_url": res.get("signed_url"),
        "agent_id": res.get("agent_id"),
        "use_direct_agent": res.get("use_direct_agent", False),
        "user_id": current_user["id"],
        "user_name": current_user.get("primeiro_nome") or current_user.get("nome")
    }


# ─── Custom LLM Endpoint (OpenAI Chat Completions SSE) ─────────────────────────

@router.post("/chat/completions")
async def eleven_custom_llm_chat_completions(
    request: Request,
    _auth: bool = Depends(verify_eleven_custom_llm_auth)
):
    """
    Endpoint Custom LLM invocado pelo ElevenAgents.
    Recebe o histórico de diálogo falado, aplica raciocínio com Meta Muse Spark Open via Baseten,
    executa as ferramentas bancárias de consulta e preparação do BankAO,
    e devolve chunks em Server-Sent Events (SSE) para o motor de voz sintetizar em tempo real.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    messages = body.get("messages", [])
    stream = body.get("stream", True)
    req_headers = dict(request.headers)

    user_id = _resolve_user_id_from_messages_or_db(messages, req_headers)

    # Identificar última mensagem do utilizador
    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            c = msg.get("content")
            if isinstance(c, str):
                user_query = c.strip()
            elif isinstance(c, list):
                # Mensagens compostas
                parts = [p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text"]
                user_query = " ".join(parts).strip()
            break

    if not user_query:
        user_query = "Olá"

    # Preparar histórico limpo para o agente BankAO
    history_cleaned = []
    for m in messages[:-1]:
        r = m.get("role")
        c = m.get("content")
        if r in ("user", "assistant") and isinstance(c, str) and c.strip():
            history_cleaned.append({"role": r, "content": c.strip()})

    logger.info("ElevenLabs Custom LLM chamado | User: %s | Pergunta: %s", user_id, user_query)

    # Executar o cérebro cognitivo com Meta Muse Spark Open
    client = get_meta_client()
    agent_res = None
    try:
        agent_res = run_agent(
            client=client,
            user_id=user_id,
            message=user_query,
            history=history_cleaned,
            client_context={"current_view": "voice-elevenlabs"}
        )
    except Exception as exc:
        logger.exception("Erro ao executar run_agent via Custom LLM: %s", exc)

    # Obter resposta e garantir síntese concisa para voz natural
    if agent_res and agent_res.get("reply"):
        reply_text = agent_res["reply"]
    else:
        # Fallback inteligente com dados do utilizador
        from backend.ai.copilot_v2 import build_user_context
        ctx = build_user_context(user_id)
        saldo_aoa = ctx.get("total_aoa", 0.0)
        reply_text = f"O seu saldo total no BankAO é de {saldo_aoa:,.2f} Kwanzas. Como posso ajudar com os seus fundos ou transferências?"

    # Limpeza para voz: remove markdown excessivo como ** ou ``` ou tabelas
    speech_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", reply_text)
    speech_text = re.sub(r"```.*?```", "", speech_text, flags=re.DOTALL)
    speech_text = re.sub(r"`([^`]+)`", r"\1", speech_text)
    speech_text = re.sub(r"#+\s*", "", speech_text)
    speech_text = speech_text.strip()

    # Se a ação foi preparada (ex: transferência), enfatizar voz de confirmação
    if agent_res and agent_res.get("action"):
        action = agent_res["action"]
        act_type = action.get("type")
        if act_type in ("TRANSFER_PREPARE", "TRANSFER_EXECUTE", "CREATE_SAVINGS_GOAL"):
            if "confirma" not in speech_text.lower():
                speech_text += " Por favor, confirme os detalhes no ecrã para autorizar a operação bancária com segurança."

    # Gerador de SSE para a ElevenLabs
    async def event_generator() -> AsyncGenerator[str, None]:
        # Divide em sentenças ou blocos de palavras para stream ultra natural
        words = speech_text.split(" ")
        chunk_size = 4  # grupos de 4 palavras para fluxo fluído de áudio
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size]) + " "
            payload = {
                "id": f"chatcmpl-eleven-{int(time.time() * 1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": settings.active_model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None
                    }
                ]
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.02)  # baixa latência

        # Chave terminal de conclusão
        final_payload = {
            "id": f"chatcmpl-eleven-{int(time.time() * 1000)}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": settings.active_model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }
            ]
        }
        yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    if stream:
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Resposta síncrona alternativa
    return JSONResponse(content={
        "id": f"chatcmpl-eleven-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": settings.active_model_name,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": speech_text
                },
                "finish_reason": "stop"
            }
        ]
    })


# ─── Webhook Tools para ElevenLabs ─────────────────────────────────────────────

class ToolWebhookRequest(BaseModel):
    user_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


@router.post("/tools/{tool_name}")
async def eleven_tool_webhook(
    tool_name: str,
    request: Request,
    _auth: bool = Depends(verify_eleven_custom_llm_auth)
):
    """
    Webhook direto para ferramentas do ElevenLabs.
    Permite que o agente execute consultas reais (saldos, movimentos, cartões, câmbios)
    ou prepare operações no BankAO.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    req_headers = dict(request.headers)
    user_id = body.get("user_id") or _resolve_user_id_from_messages_or_db([], req_headers)
    params = body.get("parameters") or body

    logger.info("ElevenLabs Webhook Tool acionada: %s para user %s | params: %s", tool_name, user_id, params)

    res = execute_tool(tool_name, params, user_id=user_id)
    return res

