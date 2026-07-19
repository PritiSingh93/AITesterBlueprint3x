"""Embed chunks (dense TEI + sparse BM25/TEI) and upsert into Qdrant.

Idempotent by design: point IDs are uuid5 of (source_type | source_path |
chunk_index), so re-running the same file overwrites the same points instead
of duplicating them. Changed files are deleted first (see run_full_ingest) so
shrinking files leave no stale tail chunks.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import List, Optional

from qdrant_client import QdrantClient, models

from common import config
from common.embedding import embed_dense, embed_sparse_docs
from ingest.chunkers.base import Chunk

# Fixed namespace — never change, or every point ID shifts and re-ingest duplicates.
_NAMESPACE = uuid.UUID("7ab0dd2e-4b1a-4c8e-9f3d-1c2b3a4d5e6f")

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=config.QDRANT_URL,
            api_key=config.QDRANT_API_KEY or None,
            timeout=60,
        )
    return _client


def ensure_collection(client: Optional[QdrantClient] = None) -> None:
    client = client or get_client()
    if client.collection_exists(config.COLLECTION):
        return
    client.create_collection(
        collection_name=config.COLLECTION,
        vectors_config={
            "dense": models.VectorParams(
                size=config.DENSE_DIM, distance=models.Distance.COSINE
            )
        },
        sparse_vectors_config={
            # IDF modifier pairs with the BM25 sparse embeddings (fastembed).
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
    for key in config.INDEXED_PAYLOAD_KEYS + ["source_path"]:
        client.create_payload_index(
            config.COLLECTION, field_name=key,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    client.create_payload_index(
        config.COLLECTION, field_name="is_failure",
        field_schema=models.PayloadSchemaType.BOOL,
    )


def point_id(source_type: str, source_path: str, index: int) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{source_type}|{source_path}|{index}"))


def upsert_chunks(chunks: List[Chunk], source_path: str, content_hash: str = "") -> int:
    """Embed and upsert one source file's chunks. Returns number of points."""
    if not chunks:
        return 0
    client = get_client()
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    total = 0
    for start in range(0, len(chunks), config.INGEST_BATCH):
        batch = chunks[start : start + config.INGEST_BATCH]
        texts = [c.text for c in batch]
        dense = embed_dense(texts)
        sparse = embed_sparse_docs(texts)

        points = []
        for offset, (chunk, dvec, (sidx, svals)) in enumerate(
            zip(batch, dense, sparse)
        ):
            index = start + offset
            source_type = chunk.metadata.get("source_type", "doc")
            payload = {
                **chunk.metadata,
                "text": chunk.text,
                "source_path": source_path,
                "chunk_index": index,
                "content_hash": content_hash,
                "ingested_at": now,
            }
            points.append(
                models.PointStruct(
                    id=point_id(source_type, source_path, index),
                    vector={
                        "dense": dvec,
                        "sparse": models.SparseVector(indices=sidx, values=svals),
                    },
                    payload=payload,
                )
            )
        client.upsert(config.COLLECTION, points=points, wait=True)
        total += len(points)
    return total


def delete_source_path(source_path: str) -> None:
    """Remove every point ingested from a given source file (delta deletions)."""
    get_client().delete(
        config.COLLECTION,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source_path", match=models.MatchValue(value=source_path)
                    )
                ]
            )
        ),
        wait=True,
    )
