"""Servicio de búsqueda híbrida por repositorio.

Construye (y cachea) los índices BM25 + vectorial a partir de los chunks
persistidos en SQLite, y devuelve resultados con cita `path:línea`.
"""

from __future__ import annotations

from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Chunk
from app.vector.bm25 import Bm25Index
from app.vector.embeddings import Embedder, get_embedder
from app.vector.hybrid import RankedResult, fuse
from app.vector.store import VectorStore, build_vector_store

_MAX_SNIPPET_CHARS = 220


class _RepoIndex:
    """Índices en memoria para un repo."""

    def __init__(self, bm25: Bm25Index, store: VectorStore, chunks: dict[int, Chunk]) -> None:
        self.bm25 = bm25
        self.store = store
        self.chunks = chunks


class SearchService:
    """Servicio de búsqueda con caché por (repo_id, chunk_count)."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or get_embedder()
        self._cache: dict[str, tuple[int, _RepoIndex]] = {}
        self._lock = Lock()

    def _load_chunks(self, session: Session, repo_id: str) -> list[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.repo_id == repo_id)
            .order_by(Chunk.index_in_repo)
        )
        return list(session.scalars(stmt).all())

    def _build(self, session: Session, repo_id: str) -> _RepoIndex:
        chunks = self._load_chunks(session, repo_id)
        ordered = sorted(chunks, key=lambda c: c.index_in_repo)
        by_id: dict[int, Chunk] = {}
        for position, chunk in enumerate(ordered):
            by_id[position] = chunk

        bm25 = Bm25Index()
        bm25.build([c.text for c in ordered])

        store = build_vector_store(self.embedder.dim)
        if ordered:
            vectors = self.embedder.encode([c.text for c in ordered])
            store.add(vectors, [str(i) for i in range(len(ordered))])

        return _RepoIndex(bm25, store, by_id)

    def _get_index(self, session: Session, repo_id: str, chunk_count: int) -> _RepoIndex:
        cached = self._cache.get(repo_id)
        if cached is not None and cached[0] == chunk_count:
            return cached[1]
        with self._lock:
            cached = self._cache.get(repo_id)
            if cached is not None and cached[0] == chunk_count:
                return cached[1]
            index = self._build(session, repo_id)
            self._cache[repo_id] = (chunk_count, index)
            return index

    def invalidate(self, repo_id: str) -> None:
        self._cache.pop(repo_id, None)

    def search(
        self,
        session: Session,
        repo_id: str,
        query: str,
        top_k: int | None = None,
    ) -> list[RankedResult]:
        k = top_k or settings.default_top_k
        chunk_count = len(self._load_chunks(session, repo_id))
        if chunk_count == 0:
            return []

        index = self._get_index(session, repo_id, chunk_count)

        bm25_hits = index.bm25.search(query, k=k * 3)
        if bm25_hits:
            query_vec = self.embedder.encode([query])[0]
            semantic_hits = index.store.search(query_vec, k=k * 3)
        else:
            semantic_hits = []

        fused = fuse(
            bm25_hits,
            semantic_hits,
            weights=settings.hybrid_weights,
            top_k=k,
        )

        results: list[RankedResult] = []
        for position, score in fused.items():
            chunk = index.chunks.get(position)
            if chunk is None:
                continue
            results.append(
                RankedResult(
                    chunk_id=chunk.id,
                    path=chunk.path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    snippet=chunk.text[:_MAX_SNIPPET_CHARS],
                    score=score,
                    bm25_score=float(bm25_hits_hint(position, bm25_hits)),
                    semantic_score=float(semantic_hint(position, semantic_hits)),
                )
            )
        return results


def bm25_hits_hint(position: int, hits: list[tuple[int, float]]) -> float:
    for idx, score in hits:
        if idx == position:
            return score
    return 0.0


def semantic_hint(position: int, hits: list[tuple[int, float]]) -> float:
    for idx, score in hits:
        if idx == position:
            return score
    return 0.0


search_service = SearchService()
