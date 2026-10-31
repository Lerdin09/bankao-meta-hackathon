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

    # Meta Model API
    MODEL_API_KEY: Optional[str] = os.getenv("MODEL_API_KEY", "")
    MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "https://api.meta.ai/v1")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "muse-spark-1.3")

    # Caminhos
    BASE_DIR: Path = BASE_DIR
    FRONTEND_DIR: Path = BASE_DIR / "frontend"
    SAMPLES_DIR: Path = BASE_DIR / "frontend" / "assets" / "samples"

    # Base de dados (caminho relativo é sempre resolvido a partir da raiz do projeto)
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bankao.db")

    @property
    def DB_FILE(self) -> Path:
        path = Path(self.DATABASE_PATH)
        return path if path.is_absolute() else BASE_DIR / path


settings = Settings()
