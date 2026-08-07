"""Health endpoints: liveness (/health) y readiness (/health/ready)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


def _liveness() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, Any]:
    """El proceso está vivo y el servidor responde."""
    return _liveness()


@router.get("/health/ready", summary="Readiness probe")
async def ready() -> dict[str, Any]:
    """La aplicación está lista para recibir tráfico.

    En F0 el readiness es best-effort: reporta el estado de Redis sin
    fallar el probe, para que la comprobación inicial del compose pase
    aunque Redis esté aún arrancando. En F1 se endurece para esperar
    dependencias reales (Redis, vector store).
    """
    import redis

    dependencies: dict[str, Any] = {}
    ready = True
    try:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        dependencies["redis"] = "ok" if client.ping() else "degraded"
        ready = ready and dependencies["redis"] == "ok"
    except Exception:
        dependencies["redis"] = "unavailable"
        ready = False

    payload = _liveness()
    payload["dependencies"] = dependencies
    payload["status"] = "ok" if ready else "degraded"
    return payload