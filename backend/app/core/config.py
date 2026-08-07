"""Aplicación y configuración central de RepoBrain (F0: esqueleto)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación vía variables de entorno / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RepoBrain"
    environment: str = "development"
    api_prefix: str = "/api"

    # Persistencia e indexación
    data_dir: str = "./data"
    workspace_root: str = "./workspace"

    # Cola de tareas (Celery + Redis)
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Seguridad (se refuerza en F3, aquí quedan los límites de diseño)
    max_upload_mb: int = 25
    request_rate_limit_per_minute: int = 60

    @property
    def is_debug(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()