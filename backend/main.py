"""
Aplicação principal FastAPI — BankAO (Meta Global AI Developer Hackathon).

Executar (a partir da raiz do projeto):
    uvicorn backend.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import api_router
from backend.core.config import settings
from backend.database import init_db
from backend.web.frontend import mount_frontend


def create_app() -> FastAPI:
    # Inicializar a base de dados e as tabelas do livro-razão
    init_db()

    application = FastAPI(
        title="BankAO API",
        description="Carteira Digital para Angola e o Mundo — Meta Global AI Developer Hackathon",
        version="1.0.0"
    )

    # Habilitar CORS para permitir testes flexíveis no navegador
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router)
    mount_frontend(application)
    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
