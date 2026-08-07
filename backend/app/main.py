"""Fábrica de la aplicación FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import health
from app.core.config import settings
from app.core.security import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Búsqueda semántica y Q&A sobre código fuente.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[{"name": "health", "description": "Probes de vida y disponibilidad"}],
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(health.router)

    return app


app = create_app()