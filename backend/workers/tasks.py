"""Tareas de Celery. La implementación real de indexación llega en F1."""

from __future__ import annotations

from workers.celery_app import celery_app


@celery_app.task(name="repobrain.noop")
def noop() -> str:
    """Tarea de humo para validar que el worker arranca y responde."""
    return "pong"