"""Tests del motor vectorial: BM25, embeddings, store y fusión híbrida."""

from __future__ import annotations

import numpy as np

from app.vector.bm25 import Bm25Index
from app.vector.embeddings import HashEmbedder
from app.vector.hybrid import fuse
from app.vector.store import NumpyVectorStore


def test_hash_embedder_is_deterministic_and_normalized() -> None:
    emb = HashEmbedder(dim=16)
    a = emb.encode(["valida el jwt del token"])
    b = emb.encode(["valida el jwt del token"])
    c = emb.encode(["otra cosa totalmente distinta"])
    assert np.allclose(a, b)
    assert np.linalg.norm(a[0]) > 0
    assert np.allclose(np.linalg.norm(a[0]), 1.0, atol=1e-3)
    # Vectores de textos distintos no deben ser idénticos
    assert not np.allclose(a[0], c[0])


def test_numpy_store_cosine_ranking() -> None:
    store = NumpyVectorStore(dim=8)
    docs = np.array(
        [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    store.add(docs, ["id0", "id1"])
    hits = store.search(np.array([1.0, 0.5, 0, 0, 0, 0, 0, 0], dtype=np.float32), k=2)
    assert hits[0][0] == "id0"
    assert hits[0][1] > hits[1][1]


def test_bm25_ranking_finds_relevant_doc() -> None:
    docs = [
        "el token se valida en auth",
        "la base de datos se conecta en db",
    ]
    bm25 = Bm25Index()
    bm25.build(docs)
    hits = bm25.search("token auth", k=2)
    assert hits[0][0] == 0
    assert hits[0][1] > 0


def test_bm25_splits_identifiers_with_underscore() -> None:
    bm25 = Bm25Index()
    bm25.build(["def soft_delete(self): marcar como borrado"])
    hits = bm25.search("soft delete", k=1)
    assert hits[0][0] == 0


def test_bm25_empty() -> None:
    bm25 = Bm25Index()
    assert bm25.search("hola", k=5) == []


def test_fuse_combines_rankings_rrf() -> None:
    bm25_hits = [(0, 5.0), (1, 1.0)]
    sem_hits = [(1, 9.0), (0, 1.0)]
    fused = fuse(bm25_hits, sem_hits, weights=(0.5, 0.5), top_k=2)
    # Doc en rank 1 en ambos => mayor score RRF
    assert fused[0] > 0.0
    assert fused[1] > 0.0
    assert list(fused.keys())[0] in (0, 1)


def test_fuse_prefers_doc_in_both_rankings() -> None:
    bm25_hits = [(1, 9.0), (2, 4.0), (0, 1.0)]
    sem_hits = [(1, 8.0), (0, 3.0), (2, 1.0)]
    fused = fuse(bm25_hits, sem_hits, weights=(0.5, 0.5), top_k=3)
    # Doc 1 es rank 1 en ambos rankings
    assert list(fused.keys())[0] == 1
    assert fused[1] > fused[2]
    assert set(fused.keys()) == {0, 1, 2}


def test_fuse_intersection() -> None:
    fused = fuse([(0, 1.0)], [(1, 1.0)], weights=(0.5, 0.5), top_k=2)
    assert set(fused.keys()) == {0, 1}
