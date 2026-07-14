from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, predictions
from app.core.config import settings


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
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(predictions.router, prefix=settings.api_prefix)
    return app


app = create_app()
