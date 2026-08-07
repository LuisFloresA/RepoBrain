"""Fábrica de la aplicación FastAPI."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, repos
from app.core.config import settings
from app.core.security import SecurityHeadersMiddleware
from app.db.session import init_db
from workers.tasks import seed_demo_repo


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        seed_demo_repo()
    except Exception:  # noqa: BLE001 - no debe tumbar el arranque si no hay demo
        app.state.demo_seed_error = True
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="Búsqueda semántica y Q&A sobre código fuente.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "health", "description": "Probes de vida y disponibilidad"},
            {"name": "repos", "description": "Repositorios, indexación y búsqueda"},
        ],
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(health.router)
    app.include_router(repos.router, prefix=settings.api_prefix)

    return app


app = create_app()
