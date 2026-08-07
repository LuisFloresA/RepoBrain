"""Esqueleto del worker Celery (F0). Las tareas de indexación llegan en F1."""

from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "repobrain",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
