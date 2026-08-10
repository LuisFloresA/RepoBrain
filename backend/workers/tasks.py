"""Tareas de Celery: indexación de repositorios (full e incremental)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db import session as db_session
from app.db.models import Chunk, Repo
from app.indexing.indexer import index_directory
from app.indexing.repo_cloner import clone_public_repo
from app.indexing.sync import SyncError, SyncResult, sync_checkout
from app.vector.embeddings import get_embedder
from app.vector.search_service import search_service
from workers.celery_app import celery_app


def _session():
    return db_session.SessionLocal()


def _checkout_for(repo: Repo):
    """Devuelve (checkout, changed_paths|None, is_full, SyncResult)."""
    if repo.source == "url":
        existing = repo.checkout_dir or ""
        if existing and Path(existing).is_dir():
            sync = sync_checkout(repo.url or "", repo.branch, existing)
            return existing, (None if sync.is_full else sync.paths), sync.is_full, sync
        checkout = clone_public_repo(repo.url or "", repo.id, branch=repo.branch)
        return checkout, None, True, SyncResult(is_full=True)
    if repo.source == "demo":
        base = Path(settings.demo_data_dir).resolve()
        if not base.is_dir():
            raise ValueError("Directorio de demo no encontrado")
        return str(base), None, True, SyncResult(is_full=True)
    if repo.source == "upload":
        base = Path(settings.workspace_root).resolve() / "uploads" / repo.id
        if not base.is_dir():
            raise ValueError("Directorio de subida no encontrado")
        return str(base), None, True, SyncResult(is_full=True)
    raise ValueError(f"Fuente desconocida: {repo.source}")


def _head_rev(checkout: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=settings.git_clone_timeout_seconds,
            check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()[:64]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _status_summary(changes: list[tuple[str, str]]) -> str:
    if not changes:
        return "sin cambios"
    first = changes[0][1]
    if len(changes) == 1:
        return f"1 archivo {first}"
    return f"{len(changes)} archivos ({first}, …)"


@celery_app.task(name="repobrain.index_repo", bind=True, max_retries=0)
def index_repo(self, repo_id: str) -> dict:
    """Indexa un repo: clona/sincroniza, parsea, trocea, embebe y persiste."""
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
            checkout, changed_paths, is_full, sync_result = _checkout_for(repo)
            repo.checkout_dir = checkout
            repo.progress = 15.0
            repo.message = "Parseando archivos con tree-sitter…"
            session.commit()

            result = index_directory(checkout, paths=changed_paths)
            changes: list[tuple[str, str]] = []

            if is_full:
                repo.file_count = len(result.files)
                repo.indexed_files = len(result.files)
                repo.skipped_files = result.skipped_total
                repo.indexed_bytes = result.indexed_bytes
            repo.progress = 45.0
            repo.message = (
                f"Generando embeddings de {len(result.chunks)} chunks…"
                if result.chunks
                else "Sin chunks nuevos que embeder…"
            )
            session.commit()

            chunk_group = result.chunks
            if is_full:
                session.execute(delete(Chunk).where(Chunk.repo_id == repo.id))
                base_index = 0
            else:
                changed = list(changed_paths or [])
                if changed:
                    stmt = delete(Chunk).where(
                        Chunk.repo_id == repo.id, Chunk.path.in_(changed)
                    )
                    session.execute(stmt)
                top = (
                    session.query(Chunk.index_in_repo)
                    .filter(Chunk.repo_id == repo.id)
                    .order_by(Chunk.index_in_repo.desc())
                    .first()
                )
                base_index = (top[0] + 1) if top else 0

            embedder = get_embedder()
            batch = settings.embed_batch_size or 64
            inserted = 0
            for start in range(0, len(chunk_group), batch):
                group = chunk_group[start : start + batch]
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
                            index_in_repo=base_index + start + i,
                        )
                    )
                    inserted += 1
                session.commit()

            repo.chunk_count = (
                session.query(Chunk).filter(Chunk.repo_id == repo.id).count()
            )
            repo.source_rev = _head_rev(checkout) if repo.source == "url" else None
            repo.last_indexed_at = datetime.now(UTC)

            lang_rows = session.execute(
                select(Chunk.language, func.count(Chunk.id).label("n"))
                .where(Chunk.repo_id == repo.id)
                .group_by(Chunk.language)
            ).all()
            by_language = {lang or "?": int(n) for lang, n in lang_rows}
            if is_full:
                repo.stats = {
                    "by_language": by_language,
                    "skipped_reasons": result.skipped_reasons,
                    "indexed_bytes": result.indexed_bytes,
                }
            elif repo.stats:
                repo.stats["by_language"] = by_language
            else:
                repo.stats = {
                    "by_language": by_language,
                    "skipped_reasons": result.skipped_reasons,
                    "indexed_bytes": result.indexed_bytes,
                }

            if repo.source == "url" and not is_full:
                sync_statuses = sync_result.statuses
                changes = sorted(sync_statuses.items())
                repo.last_changes = {
                    "full": False,
                    "count": len(changes),
                    "files": [{"path": p, "status": s} for p, s in changes] or None,
                    "commits": sync_result.commits or None,
                }
            else:
                repo.last_changes = {
                    "full": True,
                    "count": None,
                    "files": None,
                    "commits": None,
                }

            repo.progress = 100.0
            repo.status = "ready"
            msg_header = f"{repo.file_count} archivos, {repo.chunk_count} chunks"
            summary = _status_summary(changes)
            repo.message = msg_header + (f" · {summary}" if changes else "")
            session.commit()

            search_service.invalidate(repo.id)
            return {
                "status": repo.status,
                "chunks": repo.chunk_count,
                "files": repo.file_count,
                "changes": len(changes) if changes else None,
            }
        except (SyncError, ValueError, OSError) as exc:
            session.rollback()
            repo.status = "failed"
            repo.message = str(exc)[:500]
            session.commit()
            return {"status": repo.status, "error": str(exc)[:500]}
    finally:
        session.close()


def seed_demo_repo() -> str | None:
    """Crea el repo de demo pre-indexado si no existe ningún repo demo aún."""
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