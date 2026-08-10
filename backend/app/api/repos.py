"""Routers de repositorios: registro, indexación, búsqueda y visor de archivos."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ArchitectureOut,
    AskRequest,
    AskResponse,
    FileOut,
    MessageOut,
    RepoCreate,
    RepoOut,
    SearchResponse,
)
from app.architecture.map import build_architecture
from app.core.config import settings
from app.core.security import resolve_within
from app.db.models import Repo
from app.db.session import get_session
from app.indexing.parser import language_for_path
from app.vector.qa_service import qa_service
from app.vector.search_service import search_service
from workers.celery_app import celery_app
from workers.tasks import index_repo

router = APIRouter(prefix="/repos", tags=["repos"])


def _repo_or_404(session: Session, repo_id: str) -> Repo:
    repo = session.get(Repo, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repo no encontrado")
    return repo


def _enqueue_index(session: Session, repo: Repo) -> None:
    repo.status = "indexing"
    repo.progress = 0.0
    repo.message = "Encargado a la cola de indexación…"
    session.commit()
    index_repo.delay(repo.id)


@router.get("", response_model=list[RepoOut])
def list_repos(session: Session = Depends(get_session)) -> list[Repo]:
    stmt = select(Repo).order_by(Repo.created_at.desc())
    return list(session.scalars(stmt).all())


@router.post("", response_model=RepoOut, status_code=201)
def create_repo(
    payload: RepoCreate, session: Session = Depends(get_session)
) -> Repo:
    if payload.source == "url":
        if payload.url is None:
            raise HTTPException(status_code=422, detail="URL requerida para source=url")
        url = str(payload.url)
    elif payload.source == "demo":
        url = None
    else:
        raise HTTPException(status_code=422, detail="Subida no disponible en F1")

    name = payload.name or (url.rsplit("/", 1)[-1] if url else "repo")

    repo = Repo(name=name, url=url, branch=payload.branch, source=payload.source)
    session.add(repo)
    session.commit()
    session.refresh(repo)
    _enqueue_index(session, repo)
    return repo


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: str, session: Session = Depends(get_session)) -> Repo:
    return _repo_or_404(session, repo_id)


@router.get("/{repo_id}/status", response_model=RepoOut)
def get_repo_status(repo_id: str, session: Session = Depends(get_session)) -> Repo:
    return _repo_or_404(session, repo_id)


@router.post("/{repo_id}/index", response_model=RepoOut)
def trigger_index(repo_id: str, session: Session = Depends(get_session)) -> Repo:
    repo = _repo_or_404(session, repo_id)
    _enqueue_index(session, repo)
    return repo


@router.get("/{repo_id}/search", response_model=SearchResponse)
def search(
    repo_id: str,
    q: str = Query(min_length=2, max_length=200, description="Consulta en lenguaje natural"),
    top_k: int = Query(default=10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> SearchResponse:
    repo = _repo_or_404(session, repo_id)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail=f"Repo en estado: {repo.status}")

    results = search_service.search(session, repo_id, q, top_k=top_k)
    return SearchResponse(
        query=q,
        repo_id=repo_id,
        top_k=top_k,
        results=[
            {
                "chunk_id": r.chunk_id,
                "path": r.path,
                "start_line": r.start_line,
                "end_line": r.end_line,
                "snippet": r.snippet,
                "score": round(r.score, 4),
                "bm25_score": round(r.bm25_score, 4),
                "semantic_score": round(r.semantic_score, 4),
            }
            for r in results
        ],
    )


@router.post("/{repo_id}/ask", response_model=AskResponse)
def ask(
    repo_id: str,
    payload: AskRequest,
    session: Session = Depends(get_session),
) -> AskResponse:
    repo = _repo_or_404(session, repo_id)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail=f"Repo en estado: {repo.status}")

    result = qa_service.answer(session, repo, payload.question, top_k=payload.top_k)
    return AskResponse(
        question=result["question"],
        answer=result["answer"],
        citations=result["citations"],
        llm=result["llm"],
        source=result["source"],
    )


@router.get("/{repo_id}/architecture", response_model=ArchitectureOut)
def get_architecture(
    repo_id: str, session: Session = Depends(get_session)
) -> ArchitectureOut:
    repo = _repo_or_404(session, repo_id)
    if repo.status != "ready":
        raise HTTPException(status_code=409, detail=f"Repo en estado: {repo.status}")

    try:
        data = build_architecture(repo)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ArchitectureOut(
        repo_id=repo_id,
        nodes=data["nodes"],
        edges=data["edges"],
        mermaid=data["mermaid"],
        markdown=data["markdown"],
    )


@router.get("/{repo_id}/files/{path:path}", response_model=FileOut)
def get_file(repo_id: str, path: str, session: Session = Depends(get_session)) -> FileOut:
    repo = _repo_or_404(session, repo_id)
    if not repo.checkout_dir:
        raise HTTPException(status_code=409, detail="El repo aún no tiene checkout")

    try:
        file_path = resolve_within(repo.checkout_dir, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if file_path.stat().st_size > settings.max_file_bytes:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande")

    content = file_path.read_text(encoding="utf-8", errors="replace")
    return FileOut(
        path=path,
        language=language_for_path(path),
        content=content,
        line_count=len(content.splitlines()),
    )


@router.delete("/{repo_id}", response_model=MessageOut)
def delete_repo(repo_id: str, session: Session = Depends(get_session)) -> MessageOut:
    repo = _repo_or_404(session, repo_id)
    # Limpieza best-effort del checkout dentro del workspace
    if repo.checkout_dir:
        try:
            base = Path(settings.workspace_root).resolve()
            checkout = resolve_within(base, repo_id)
            import shutil

            if checkout.exists():
                shutil.rmtree(checkout)
        except (ValueError, OSError):
            pass
    search_service.invalidate(repo_id)
    session.delete(repo)
    session.commit()
    return MessageOut(message="Repo eliminado")


@router.get("/worker/ping", include_in_schema=False)
def worker_ping() -> dict:
    result = celery_app.send_task("repobrain.noop")
    return {"result": result.get(timeout=10)}
