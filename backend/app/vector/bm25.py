"""Índice BM25 sobre los chunks de un repo (bm25s).

Tokenización pensada para código: los identificadores con `_` se parten
(`soft_delete` -> `soft delete`), y no se aplican stopwords en inglés (que
borrarían términos de código como `for`, `in`, `as`).
"""

from __future__ import annotations

import bm25s

_TOKEN_PATTERN = r"[a-z0-9]+"


class Bm25Index:
    """Wrapper de bm25s: índice por repo sobre textos de chunks."""

    def __init__(self, documents: list[str] | None = None) -> None:
        self._docs = documents or []
        self._retriever: bm25s.BM25 | None = None

    @property
    def size(self) -> int:
        return len(self._docs)

    @staticmethod
    def _tokenize(texts: list[str]):
        return bm25s.tokenize(
            texts,
            token_pattern=_TOKEN_PATTERN,
            stopwords=None,
            show_progress=False,
            leave=False,
        )

    def build(self, documents: list[str]) -> None:
        self._docs = list(documents)
        if not self._docs:
            self._retriever = None
            return
        retriever = bm25s.BM25(k1=1.5, b=0.75)
        retriever.index(self._tokenize(self._docs))
        self._retriever = retriever

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Devuelve [(doc_index, score)] ordenados por relevancia."""
        if self._retriever is None or k <= 0 or not self._docs:
            return []
        safe_k = min(k, len(self._docs))
        results, scores = self._retriever.retrieve(
            self._tokenize([query]), k=safe_k
        )
        hits = [
            (int(i), float(s))
            for i, s in zip(results[0], scores[0], strict=False)
            if i >= 0
        ]
        return hits

    def build_from(self, texts: list[str]) -> None:
        self.build(texts)
