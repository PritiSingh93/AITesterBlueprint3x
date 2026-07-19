"""Embedding clients: dense via TEI (BGE-M3), sparse via BM25/fastembed or TEI.

Dense:  POST {TEI_EMBED_URL}/embed        -> [[float; 1024], ...]
Sparse: default BM25 through fastembed (Qdrant/bm25 model) because TEI does not
        expose BGE-M3's learned sparse head. With SPARSE_BACKEND=tei we call
        POST {TEI_SPARSE_URL}/embed_sparse (requires a SPLADE-family model).
"""
from __future__ import annotations

from typing import List, Tuple

import httpx

from common import config

SparseVec = Tuple[List[int], List[float]]  # (indices, values)

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


# --------------------------------------------------------------------------- #
# Dense (TEI / BGE-M3)                                                         #
# --------------------------------------------------------------------------- #
def embed_dense(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts (<= INGEST_BATCH) into dense vectors."""
    resp = httpx.post(
        f"{config.TEI_EMBED_URL}/embed",
        json={"inputs": texts, "truncate": True},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------- #
# Sparse                                                                       #
# --------------------------------------------------------------------------- #
_bm25 = None


def _get_bm25():
    global _bm25
    if _bm25 is None:
        from fastembed import SparseTextEmbedding  # lazy: heavy import

        _bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")
    return _bm25


def _tei_sparse(texts: List[str]) -> List[SparseVec]:
    resp = httpx.post(
        f"{config.TEI_SPARSE_URL}/embed_sparse",
        json={"inputs": texts, "truncate": True},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    out: List[SparseVec] = []
    for row in resp.json():
        out.append(([t["index"] for t in row], [t["value"] for t in row]))
    return out


def embed_sparse_docs(texts: List[str]) -> List[SparseVec]:
    if config.SPARSE_BACKEND == "tei":
        return _tei_sparse(texts)
    return [
        (list(e.indices), list(e.values)) for e in _get_bm25().embed(texts)
    ]


def embed_sparse_query(text: str) -> SparseVec:
    if config.SPARSE_BACKEND == "tei":
        return _tei_sparse([text])[0]
    e = next(_get_bm25().query_embed(text))
    return (list(e.indices), list(e.values))


# --------------------------------------------------------------------------- #
# Rerank (TEI / bge-reranker-v2-m3)                                            #
# --------------------------------------------------------------------------- #
def rerank(query: str, texts: List[str]) -> List[dict]:
    """Return [{"index": int, "score": float}, ...] sorted by score desc."""
    resp = httpx.post(
        f"{config.TEI_RERANK_URL}/rerank",
        json={"query": query, "texts": texts, "truncate": True},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return sorted(resp.json(), key=lambda r: r["score"], reverse=True)
