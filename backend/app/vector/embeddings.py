"""Generación de embeddings locales (sin API key).

- SentenceEmbedder: `all-MiniLM-L6-v2` con sentence-transformers (calidad).
- HashEmbedder: fallback determinista sin modelo (tests / modo ligero).
"""

from __future__ import annotations

import hashlib
import re
from threading import Lock

import numpy as np

from app.core.config import settings

_WORD_RE = re.compile(r"[a-z0-9_]+")


class Embedder:
    """Contrato de embedder."""

    dim: int

    def encode(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class SentenceEmbedder(Embedder):
    """Embeddings reales con all-MiniLM-L6-v2, cargado de forma perezosa."""

    def __init__(self, model_name: str | None = None, batch_size: int = 64) -> None:
        self.model_name = model_name or settings.embedding_model
        self.batch_size = batch_size or settings.embed_batch_size
        self.dim = settings.embedding_dim
        self._model = None
        self._lock = Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        model = self._load()
        return model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)


class HashEmbedder(Embedder):
    """Embedder determinista de baja calidad (fallback sin modelo)."""

    def __init__(self, dim: int | None = None, seed: int = 42) -> None:
        self.dim = dim or settings.embedding_dim
        self._seed = seed
        self._hashes: dict[str, tuple[int, ...]] = {}

    def _token_hashes(self, text: str) -> list[tuple[int, int]]:
        tokens = _WORD_RE.findall(text.lower())
        hashes: list[tuple[int, int]] = []
        for token in tokens:
            key = hashlib.blake2b(token.encode(), digest_size=4).hexdigest()
            h = int(key, 16)
            sign = 1 if h & 1 else -1
            hashes.append((h >> 1, sign))
        return hashes

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for h, sign in self._token_hashes(text):
                vecs[i, h % self.dim] += sign
            norm = np.linalg.norm(vecs[i])
            if norm > 0:
                vecs[i] /= norm
        return vecs


_embedder: Embedder | None = None
_embedder_lock = Lock()


def get_embedder() -> Embedder:
    """Devuelve el embedder singleton según configuración."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                if settings.embedder_backend == "hash":
                    _embedder = HashEmbedder()
                else:
                    _embedder = SentenceEmbedder()
    return _embedder
