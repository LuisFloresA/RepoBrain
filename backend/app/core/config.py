"""Aplicación y configuración central de RepoBrain."""

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
    demo_data_dir: str = "./demo/data"
    db_path: str = ""

    # Cola de tareas (Celery + Redis)
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Embeddings: "sentence-transformers" (all-MiniLM-L6-v2) o "hash" (fallback sin modelo)
    embedder_backend: str = "sentence-transformers"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    # Tamaño de batch al generar embeddings (control de memoria del worker)
    embed_batch_size: int = 64

    # Límites y seguridad (se refuerzan en F3)
    max_upload_mb: int = 25
    request_rate_limit_per_minute: int = 60
    max_repo_files: int = 5000
    max_file_bytes: int = 2 * 1024 * 1024  # 2 MB por archivo
    git_clone_timeout_seconds: int = 60

    # Búsqueda
    default_top_k: int = 10
    hybrid_weights: tuple[float, float] = (0.5, 0.5)  # (bm25, semántico)

    @property
    def is_debug(self) -> bool:
        return self.environment == "development"

    @property
    def sqlite_path(self) -> str:
        return self.db_path or f"{self.data_dir}/repobrain.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()