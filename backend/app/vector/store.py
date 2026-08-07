"""Almacén vectorial: FAISS con fallback a numpy (coseno)."""

from __future__ import annotations

from typing import Protocol

import numpy as np

try:
    import faiss  # type: ignore

    _FAISS_AVAILABLE = True
except Exception:  # pragma: no cover - fallback de entorno
    faiss = None  # type: ignore
    _FAISS_AVAILABLE = False


class VectorStore(Protocol):
    """Contrato del store vectorial."""

    def add(self, vectors: np.ndarray, ids: list[str]) -> None: ...

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]: ...

    @property
    def size(self) -> int: ...


def _normalize(vectors: np.ndarray) -> np.ndarray:
    vecs = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return np.divide(vecs, norms, out=vecs, where=norms > 0)


class FaissVectorStore:
    """Índice FAISS (IndexFlatIP sobre vectores normalizados => coseno)."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)
        self._ids: list[str] = []

    @property
    def size(self) -> int:
        return len(self._ids)

    def add(self, vectors: np.ndarray, ids: list[str]) -> None:
        self.index.add(_normalize(vectors))
        self._ids.extend(ids)

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        if self.size == 0 or k <= 0:
            return []
        scores, idx = self.index.search(
            _normalize(np.asarray([vector], dtype=np.float32)), k
        )
        hits = [
            (self._ids[i], float(s))
            for i, s in zip(idx[0], scores[0], strict=False)
            if i >= 0
        ]
        return hits


class NumpyVectorStore:
    """Fallback sin FAISS: producto punto sobre vectores normalizados."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._vectors = np.zeros((0, dim), dtype=np.float32)
        self._ids: list[str] = []

    @property
    def size(self) -> int:
        return len(self._ids)

    def add(self, vectors: np.ndarray, ids: list[str]) -> None:
        self._vectors = np.vstack([self._vectors, _normalize(vectors)])
        self._ids.extend(ids)

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        if self.size == 0 or k <= 0:
            return []
        q = _normalize(np.asarray([vector], dtype=np.float32))[0]
        scores = self._vectors @ q
        order = np.argsort(-scores)[:k]
        return [(self._ids[i], float(scores[i])) for i in order]


def build_vector_store(dim: int) -> VectorStore:
    """Devuelve el store disponible (FAISS si está instalado, si no numpy)."""
    if _FAISS_AVAILABLE:
        return FaissVectorStore(dim)
    return NumpyVectorStore(dim)
