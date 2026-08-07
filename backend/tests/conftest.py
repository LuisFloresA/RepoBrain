"""Fixtures compartidos: entorno de prueba aislado (DB temporal, hash embeddings)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Aísla settings + DB + embedder para cada test."""
    from app.core.config import settings

    workspace = tmp_path / "workspace"
    data = tmp_path / "data"
    demo = tmp_path / "demo"
    workspace.mkdir()
    data.mkdir()
    demo.mkdir()

    monkeypatch.setattr(settings, "workspace_root", str(workspace))
    monkeypatch.setattr(settings, "data_dir", str(data))
    monkeypatch.setattr(settings, "demo_data_dir", str(demo))
    monkeypatch.setattr(settings, "db_path", str(data / "test.db"))
    monkeypatch.setattr(settings, "embedder_backend", "hash")
    monkeypatch.setattr(settings, "embed_batch_size", 16)

    import app.vector.embeddings as embeddings
    from app.vector.search_service import search_service

    embeddings._embedder = None
    assert isinstance(embeddings.get_embedder(), embeddings.HashEmbedder)
    search_service._cache.clear()
    search_service.embedder = embeddings.HashEmbedder()

    from app.db import session as db_session
    from app.db.models import Base

    engine = create_engine(
        f"sqlite:///{settings.sqlite_path}",
        connect_args={"check_same_thread": False},
    )
    db_session.engine = engine
    db_session.SessionLocal = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    Base.metadata.create_all(bind=engine)

    yield {
        "workspace": workspace,
        "data": data,
        "demo": demo,
    }


@pytest.fixture()
def sync_index(monkeypatch):
    """Ejecuta la tarea de indexación de forma síncrona (sin Celery/Redis)."""
    import types

    import app.api.repos as repos_module
    import workers.tasks as tasks_module

    original = tasks_module.index_repo

    def fake_delay(repo_id: str):
        return original(repo_id)

    fake_task = types.SimpleNamespace(delay=fake_delay)
    monkeypatch.setattr(tasks_module, "index_repo", fake_task)
    monkeypatch.setattr(repos_module, "index_repo", fake_task)
    return fake_task


@pytest.fixture()
def client(env, sync_index):
    from fastapi.testclient import TestClient

    from app.main import app

    # El seed de demo no debe correr en tests
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


def make_demo_repo(demo_dir: Path) -> None:
    """Crea un mini repo de código de ejemplo dentro de demo_dir."""
    app_dir = demo_dir / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "auth.py").write_text(
        "import jwt\n"
        "\n"
        "def verify_jwt(token):\n"
        "    payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])\n"
        "    return payload\n"
    )
    (app_dir / "db.py").write_text(
        "from sqlalchemy import create_engine\n"
        "\n"
        "engine = create_engine('postgresql://app:secret@db/loginapi')\n"
    )
    (app_dir / "server.js").write_text(
        "function handleLogin(req, res) {\n"
        "  const token = signJwt(req.body.email);\n"
        "  res.json({ token });\n"
        "}\n"
    )
