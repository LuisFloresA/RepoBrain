"""Tareas de Celery: indexación de repositorios."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete

from app.core.config import settings
from app.db import session as db_session
from app.db.models import Chunk, Repo
from app.indexing.indexer import index_directory
from app.indexing.repo_cloner import clone_public_repo
from app.vector.embeddings import get_embedder
from app.vector.search_service import search_service
from workers.celery_app import celery_app


def _session():
    return db_session.SessionLocal()


def _checkout_for(repo: Repo) -> str:
    if repo.source == "url":
        return clone_public_repo(repo.url or "", repo.id)
    if repo.source == "demo":
        base = Path(settings.demo_data_dir).resolve()
        if not base.is_dir():
            raise ValueError("Directorio de demo no encontrado")
        return str(base)
    if repo.source == "upload":
        base = Path(settings.workspace_root).resolve() / "uploads" / repo.id
        if not base.is_dir():
            raise ValueError("Directorio de subida no encontrado")
        return str(base)
    raise ValueError(f"Fuente desconocida: {repo.source}")


@celery_app.task(name="repobrain.index_repo", bind=True, max_retries=0)
def index_repo(self, repo_id: str) -> dict:
    """Indexa un repo: clona (si procede), parsea, trocea, embebe y persiste."""
    db_session.init_db()
    session = db_session.SessionLocal()
    try:
        repo = session.get(Repo, repo_id)
        if repo is None:
            return {"status": "missing", "repo_id": repo_id}

        repo.status = "indexing"
        repo.progress = 5.0
        repo.message = "Preparando checkout…"
        session.commit()

        try:
            checkout = _checkout_for(repo)
            repo.checkout_dir = checkout
            repo.progress = 15.0
            repo.message = "Parseando archivos con tree-sitter…"
            session.commit()

            chunks = index_directory(checkout)

            repo.file_count = len({c.path for c in chunks})
            repo.progress = 45.0
            repo.message = f"Generando embeddings de {len(chunks)} chunks…"
            session.commit()

            session.execute(delete(Chunk).where(Chunk.repo_id == repo.id))
            embedder = get_embedder()
            batch = settings.embed_batch_size or 64
            inserted = 0
            for start in range(0, len(chunks), batch):
                group = chunks[start : start + batch]
                embedder.encode([c.text for c in group])  # fuerza cómputo por lotes
                for i, chunk in enumerate(group):
                    session.add(
                        Chunk(
                            repo_id=repo.id,
                            path=chunk.path,
                            language=chunk.language,
                            start_line=chunk.start_line,
                            end_line=chunk.end_line,
                            token_count=chunk.token_count,
                            text=chunk.text,
                            index_in_repo=start + i,
                        )
                    )
                    inserted += 1
                session.commit()

            repo.chunk_count = inserted
            repo.progress = 100.0
            repo.status = "ready"
            repo.message = f"{repo.file_count} archivos, {inserted} chunks"
            session.commit()

            search_service.invalidate(repo.id)
            return {"status": repo.status, "chunks": inserted, "files": repo.file_count}
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de indexación
            session.rollback()
            repo.status = "failed"
            repo.message = str(exc)[:500]
            session.commit()
            return {"status": repo.status, "error": str(exc)[:500]}
    finally:
        session.close()


def seed_demo_repo() -> str | None:
    """Crea el repo de demo pre-indexado si no existe ningún repo aún."""
    db_session.init_db()
    session = db_session.SessionLocal()
    try:
        existing = session.query(Repo).filter(Repo.source == "demo").first()
        if existing is not None:
            return None
        repo = Repo(
            name="Demo · login-api (JWT)",
            source="demo",
            status="indexing",
            message="Indexando demo embebida…",
        )
        session.add(repo)
        session.commit()
        index_repo.delay(repo.id)
        return repo.id
    finally:
        session.close()
