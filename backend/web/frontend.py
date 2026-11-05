"""
Servir o frontend: ficheiros estáticos em /static e o index.html montado a partir dos partials em /.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.core.config import settings
from backend.web.includes import CachedPage


class NoCacheStaticFiles(StaticFiles):
    """Ficheiros estáticos que o navegador revalida sempre (evita o telemóvel ficar com JS/CSS antigos)."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def mount_frontend(app: FastAPI) -> None:
    root = settings.FRONTEND_DIR
    if not root.exists():
        return

    app.mount("/static", NoCacheStaticFiles(directory=root), name="static")
    page = CachedPage(root / "index.html", root)

    @app.get("/manifest.json")
    def serve_manifest():
        manifest_path = root / "manifest.json"
        if manifest_path.exists():
            return FileResponse(manifest_path, media_type="application/manifest+json")
        return {}

    @app.get("/sw.js")
    def serve_sw():
        sw_path = root / "sw.js"
        if sw_path.exists():
            return FileResponse(sw_path, media_type="application/javascript")
        return ""

    tools_dir = settings.BASE_DIR / "tools"

    @app.get("/documento")
    @app.get("/documentos")
    def serve_documento():
        doc_path = tools_dir / "gerar_documentos.html"
        if doc_path.exists():
            return FileResponse(doc_path, media_type="text/html")
        return HTMLResponse("<h1>Gerador de documentos não encontrado</h1>", status_code=404)

    @app.get("/passaporte")
    @app.get("/passaportes")
    def serve_passaporte():
        pass_path = tools_dir / "gerar_passaportes.html"
        if pass_path.exists():
            return FileResponse(pass_path, media_type="text/html")
        return HTMLResponse("<h1>Gerador de passaportes não encontrado</h1>", status_code=404)

    @app.get("/")
    def serve_index():
        # `page.get()` volta a montar o HTML sempre que um partial é alterado
        return HTMLResponse(page.get())
