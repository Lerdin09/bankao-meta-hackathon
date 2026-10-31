"""
Servir o frontend: ficheiros estáticos em /static e o index.html montado a partir dos partials em /.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.web.includes import CachedPage


def mount_frontend(app: FastAPI) -> None:
    root = settings.FRONTEND_DIR
    if not root.exists():
        return

    app.mount("/static", StaticFiles(directory=root), name="static")
    page = CachedPage(root / "index.html", root)

    @app.get("/")
    def serve_index():
        # `page.get()` volta a montar o HTML sempre que um partial é alterado
        return HTMLResponse(page.get())
