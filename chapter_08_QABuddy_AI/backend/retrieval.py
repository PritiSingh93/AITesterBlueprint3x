"""Hybrid retrieval: dense + sparse -> Qdrant server-side RRF fusion ->
bge-reranker-v2-m3 (TEI) cross-encoder -> top-k chunks with metadata.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from qdrant_client import models

from common import config
from common.embedding import embed_dense, embed_sparse_query, rerank
from ingest.embed_and_upsert import get_client


def build_filter(filters: Optional[Dict]) -> Optional[models.Filter]:
    """{"source_type": ["jira", "test_case"], "module": "checkout"} -> Filter."""
    if not filters:
        return None
    must = []
    for key, value in filters.items():
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            must.append(
                models.FieldCondition(key=key, match=models.MatchAny(any=value))
            )
        else:
            must.append(
                models.FieldCondition(key=key, match=models.MatchValue(value=value))
            )
    return models.Filter(must=must) if must else None


def retrieve(
    question: str,
    filters: Optional[Dict] = None,
    top_k: Optional[int] = None,
) -> List[Dict]:
    top_k = top_k or config.TOP_K_RERANK
    qfilter = build_filter(filters)

    dense = embed_dense([question])[0]
    sidx, svals = embed_sparse_query(question)

    prefetch = [
        models.Prefetch(
            query=dense, using="dense", limit=config.TOP_N_HYBRID, filter=qfilter
        )
    ]
    if sidx:  # all-stopword queries can produce an empty sparse vector
        prefetch.append(
            models.Prefetch(
                query=models.SparseVector(indices=sidx, values=svals),
                using="sparse",
                limit=config.TOP_N_HYBRID,
                filter=qfilter,
            )
        )

    result = get_client().query_points(
        config.COLLECTION,
        prefetch=prefetch,
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=config.TOP_N_HYBRID,
        with_payload=True,
    )
    candidates = result.points
    if not candidates:
        return []

    ranked = rerank(question, [p.payload.get("text", "") for p in candidates])
    return [
        {"score": float(r["score"]), "payload": candidates[r["index"]].payload}
        for r in ranked[:top_k]
    ]


def source_label(payload: Dict) -> str:
    """The citation handle for a chunk: jira key, tc id, or file path."""
    return (
        payload.get("jira_key")
        or payload.get("tc_id")
        or payload.get("file_path")
        or payload.get("source_path")
        or "?"
    )
