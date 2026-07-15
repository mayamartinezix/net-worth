from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import health, predictions
from app.core.config import settings

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Monte Carlo tournament prediction API for FIFA World Cup and UEFA Euros. "
            "Match model: Poisson goals with Elo features. Odds are batch-simulated."
        ),
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(predictions.router, prefix=settings.api_prefix)

    if FRONTEND_DIST.exists():
        assets = FRONTEND_DIST / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

        @app.get("/app")
        def app_index() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

        @app.get("/staging")
        def staging() -> FileResponse:
            path = FRONTEND_DIST / "staging.html"
            if not path.exists():
                raise HTTPException(status_code=404, detail="Staging build not found")
            return FileResponse(path)

        @app.get("/favicon.ico")
        def favicon() -> None:
            raise HTTPException(status_code=404)

    return app


app = create_app()
