"""
YTSPERBOT - FastAPI App
Serve l'API REST e la React webapp (static files).
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from api.routes import (
    dashboard,
    youtube,
    social,
    trends,
    pinterest,
    news,
    reddit,
    twitter,
    config,
    system,
)
from api.deps import verify_token
from fastapi import Depends

WEBAPP_DIST = os.path.join(os.path.dirname(__file__), "..", "webapp", "dist")


def create_app() -> FastAPI:
    app = FastAPI(title="YTSPERBOT API", version="2.0.0", docs_url="/api/docs")

    # CORS — in produzione limita alle origini necessarie
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routes (tutte protette da DASHBOARD_TOKEN) ────────
    auth = [Depends(verify_token)]
    app.include_router(dashboard.router, prefix="/api", dependencies=auth)
    app.include_router(youtube.router, prefix="/api", dependencies=auth)
    app.include_router(social.router, prefix="/api", dependencies=auth)
    app.include_router(trends.router, prefix="/api", dependencies=auth)
    app.include_router(pinterest.router, prefix="/api", dependencies=auth)
    app.include_router(news.router, prefix="/api", dependencies=auth)
    app.include_router(reddit.router, prefix="/api", dependencies=auth)
    app.include_router(twitter.router, prefix="/api", dependencies=auth)
    app.include_router(config.router, prefix="/api", dependencies=auth)
    app.include_router(system.router, prefix="/api", dependencies=auth)

    # ── Health check (UptimeRobot / monitoring tools) ────────
    @app.get("/", include_in_schema=False)
    @app.head("/", include_in_schema=False)
    def health():
        return "OK"

    @app.get("/api/health", tags=["system"], include_in_schema=True)
    def health_json():
        """Endpoint JSON per monitoring tools (non richiede autenticazione)."""
        from datetime import datetime, timezone

        return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

    # ── React static files ────────────────────────────────────
    if os.path.isdir(WEBAPP_DIST):
        app.mount(
            "/assets",
            StaticFiles(directory=os.path.join(WEBAPP_DIST, "assets")),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            # Non intercettare le route /api
            if full_path.startswith("api"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            index = os.path.join(WEBAPP_DIST, "index.html")
            if os.path.exists(index):
                return FileResponse(index)
            return JSONResponse(
                {"detail": "Frontend non ancora buildato"}, status_code=503
            )

    return app
