"""
Cliente da Meta Model API (compatível com OpenAI).
Devolve None quando não existe chave configurada — os módulos de IA usam então o fallback local.
"""
from typing import Optional

from openai import OpenAI

from backend.core.config import settings


def get_meta_client() -> Optional[OpenAI]:
    api_key = settings.MODEL_API_KEY
    if not api_key or api_key == "your_meta_model_api_key_here":
        return None
    return OpenAI(
        api_key=api_key,
        base_url=settings.MODEL_BASE_URL
    )
