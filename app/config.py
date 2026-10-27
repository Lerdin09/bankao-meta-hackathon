import os
from typing import Optional
from dotenv import load_dotenv

# Carregar variáveis do arquivo .env
load_dotenv()

class Settings:
    PORT: int = int(os.getenv("PORT", "8000"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "bankao_dev_secret_key_change_in_prod")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 dia

    # Meta Model API
    MODEL_API_KEY: Optional[str] = os.getenv("MODEL_API_KEY", "")
    MODEL_BASE_URL: str = os.getenv("MODEL_BASE_URL", "https://api.meta.ai/v1")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "muse-spark-1.3")

    # DB
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bankao.db")

settings = Settings()
