"""Fusión de rankings BM25 (léxico) y semántico (coseno sobre embeddings).

Usa Reciprocal Rank Fusion (RRF): se combinan las posiciones de cada
documento en ambos rankings, sin depender de la escala de las puntuaciones
(cada motor puntúa de forma distinta). Robusto con corpora pequeños.
"""

from __future__ import annotations

from dataclasses import dataclass

_RRF_K = 60


@dataclass
class RankedResult:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    bm25_score: float
    semantic_score: float


def _rrf_score(rank: int) -> float:
    # rank es 0-based => contribución 1/(K + rank + 1)
    return 1.0 / (_RRF_K + rank + 1)


def fuse(
    bm25_hits: list[tuple[int, float]],
    semantic_hits: list[tuple[int, float]],
    weights: tuple[float, float] = (0.5, 0.5),
    top_k: int = 10,
) -> dict[int, float]:
    """Fusiona dos rankings (sobre el mismo id-chunk) mediante RRF."""
    w_bm25, w_vec = weights
    fused: dict[int, float] = {}

    for rank, (idx, _) in enumerate(bm25_hits):
        fused[idx] = fused.get(idx, 0.0) + w_bm25 * _rrf_score(rank)
    for rank, (idx, _) in enumerate(semantic_hits):
        fused[idx] = fused.get(idx, 0.0) + w_vec * _rrf_score(rank)

    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    return dict(ranked[:top_k])
