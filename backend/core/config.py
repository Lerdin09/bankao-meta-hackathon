"""
Configuração central da aplicação (variáveis de ambiente + caminhos do projeto).
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Carregar variáveis do ficheiro .env
load_dotenv()

# Raiz do projeto (pasta que contém backend/ e frontend/)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "bankao_dev_secret_key_change_in_prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 dia

    # ─── Provedores de IA (Baseten & Meta Muse Spark Open) ────────────────────
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "auto")  # "auto", "baseten", "meta"

    # Baseten (Meta Muse Spark Open - Meta Global AI Developer Hackathon)
    BASETEN_API_KEY: Optional[str] = os.getenv("BASETEN_API_KEY", "")
    BASETEN_BASE_URL: str = os.getenv("BASETEN_BASE_URL", "https://inference.baseten.co/v1")
    BASETEN_MODEL: str = os.getenv("BASETEN_MODEL", "meta-models/muse-spark-open-1026")

    # Meta Model API (Direct / Fallback genérico)
    MODEL_API_KEY: Optional[str] = os.getenv("MODEL_API_KEY", "")
    MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "https://inference.baseten.co/v1")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "meta-models/muse-spark-open-1026")

    # Parâmetros de Inferência & Reasoning (Muse Spark Open)
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "3500"))
    AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.2"))
    AI_REQUEST_TIMEOUT: int = int(os.getenv("AI_REQUEST_TIMEOUT", "45"))
    AI_ENABLE_REASONING_TRACE: bool = os.getenv("AI_ENABLE_REASONING_TRACE", "true").lower() in ("true", "1", "yes")

    # ElevenLabs (voz conversacional — opt-in)
    ELEVENLABS_API_KEY: Optional[str] = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_AGENT_ID: Optional[str] = os.getenv("ELEVENLABS_AGENT_ID", "")
    ELEVENLABS_CUSTOM_LLM_SECRET: Optional[str] = os.getenv("ELEVENLABS_CUSTOM_LLM_SECRET", "")

    # Caminhos
    BASE_DIR: Path = BASE_DIR
    FRONTEND_DIR: Path = BASE_DIR / "frontend"

    # Base de dados (caminho relativo é sempre resolvido a partir da raiz do projeto)
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bankao.db")

    @property
    def DB_FILE(self) -> Path:
        path = Path(self.DATABASE_PATH)
        return path if path.is_absolute() else BASE_DIR / path

    @property
    def active_ai_provider(self) -> str:
        """Determina o provedor ativo baseado nas chaves e configuração."""
        pref = (self.AI_PROVIDER or "auto").lower().strip()
        if pref in ("baseten", "meta"):
            return pref
        # Modo 'auto': se tem BASETEN_API_KEY ou a BASE_URL aponta para baseten, usa baseten
        if self.BASETEN_API_KEY:
            return "baseten"
        if "baseten.co" in (self.MODEL_BASE_URL or ""):
            return "baseten"
        if self.MODEL_API_KEY and not self.MODEL_API_KEY.startswith("LLM_"):
            return "baseten"
        if self.MODEL_API_KEY:
            return "meta"
        return "offline"

    @property
    def active_api_key(self) -> str:
        """Retorna a chave correspondente ao provedor ativo."""
        if self.active_ai_provider == "baseten":
            return (self.BASETEN_API_KEY or self.MODEL_API_KEY or "").strip()
        return (self.MODEL_API_KEY or self.BASETEN_API_KEY or "").strip()

    @property
    def active_base_url(self) -> str:
        """Retorna a base URL correspondente ao provedor ativo."""
        if self.active_ai_provider == "baseten":
            return self.BASETEN_BASE_URL or "https://inference.baseten.co/v1"
        return self.MODEL_BASE_URL or "https://api.meta.ai/v1"

    @property
    def active_model_name(self) -> str:
        """Retorna o modelo correspondente ao provedor ativo."""
        if self.active_ai_provider == "baseten":
            return self.BASETEN_MODEL or "meta-models/muse-spark-open-1026"
        return self.MODEL_NAME or "muse-spark-1.3"

    @property
    def is_ai_configured(self) -> bool:
        """Verifica se existe chave de API configurada válida."""
        key = self.active_api_key
        return bool(key and key not in ("your_meta_model_api_key_here", "YOUR_API_KEY", ""))


settings = Settings()
