"""Qdrant vector store — native dense + sparse vectors, filters, and RRF.

Runs **embedded** by default (a local file store at ``QDRANT_PATH``) so no
Docker is required. Set ``QDRANT_URL`` to point at a Qdrant server instead.

The collection ``vwo_test_cases`` holds two named vectors per point:

* ``dense``  — 1024-d bge-m3 embedding, cosine distance
* ``sparse`` — bge-m3 lexical weights (token-id -> weight)

We run the dense and sparse searches *separately* (so the UI can show each
ranked list) and fuse them with Reciprocal Rank Fusion in Python.
"""

from __future__ import annotations

import threading
import uuid

from qdrant_client import QdrantClient, models

from . import config

_NS = uuid.UUID("6f9c2a10-4d3b-4b7a-9f2e-000000000001")
_client: QdrantClient | None = None
_lock = threading.Lock()


def point_uuid(chunk_id: str) -> str:
    """Stable UUID for a string chunk id (Qdrant needs int/UUID ids)."""
    return str(uuid.uuid5(_NS, chunk_id))


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                if config.QDRANT_URL:
                    _client = QdrantClient(url=config.QDRANT_URL)
                else:
                    config.QDRANT_PATH.mkdir(parents=True, exist_ok=True)
                    _client = QdrantClient(path=str(config.QDRANT_PATH))
    return _client


def collection_exists() -> bool:
    try:
        return get_client().collection_exists(config.COLLECTION_NAME)
    except Exception:
        return False


def recreate_collection(dim: int = config.DENSE_DIM) -> None:
    """Drop and recreate the collection with dense + sparse vector configs."""
    client = get_client()
    if client.collection_exists(config.COLLECTION_NAME):
        client.delete_collection(config.COLLECTION_NAME)
    client.create_collection(
        collection_name=config.COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(size=dim, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                index=models.SparseIndexParams(on_disk=False),
            ),
        },
    )


def ensure_collection(dim: int = config.DENSE_DIM) -> None:
    if not collection_exists():
        recreate_collection(dim)


def upsert(points: list[dict]) -> None:
    """``points``: list of {id, dense, sparse_indices, sparse_values, payload}."""
    client = get_client()
    structs = []
    for p in points:
        structs.append(
            models.PointStruct(
                id=point_uuid(p["id"]),
                vector={
                    "dense": p["dense"],
                    "sparse": models.SparseVector(
                        indices=p["sparse_indices"],
                        values=p["sparse_values"],
                    ),
                },
                payload=p["payload"],
            )
        )
    client.upsert(collection_name=config.COLLECTION_NAME, points=structs, wait=True)


def count() -> int:
    try:
        return get_client().count(config.COLLECTION_NAME, exact=True).count
    except Exception:
        return 0


def collection_info() -> dict:
    client = get_client()
    if not client.collection_exists(config.COLLECTION_NAME):
        return {"exists": False, "points": 0}
    info = client.get_collection(config.COLLECTION_NAME)
    return {
        "exists": True,
        "name": config.COLLECTION_NAME,
        "points": count(),
        "status": str(getattr(info, "status", "")),
        "vectors": ["dense (1024, cosine)", "sparse (bge-m3 lexical)"],
        "storage": "embedded file store" if not config.QDRANT_URL else config.QDRANT_URL,
    }


# --------------------------------------------------------------------------- #
# Filters                                                                      #
# --------------------------------------------------------------------------- #
def build_filter(filters: dict | None) -> models.Filter | None:
    if not filters:
        return None
    must = []
    for key, value in filters.items():
        if value in (None, "", []):
            continue
        must.append(
            models.FieldCondition(key=key, match=models.MatchValue(value=value))
        )
    return models.Filter(must=must) if must else None


def _hit_to_dict(hit) -> dict:
    payload = hit.payload or {}
    return {
        "id": payload.get("chunk_id", str(hit.id)),
        "score": float(hit.score) if hit.score is not None else 0.0,
        "text": payload.get("text", ""),
        "payload": payload,
    }


# --------------------------------------------------------------------------- #
# Search                                                                       #
# --------------------------------------------------------------------------- #
def dense_search(dense_vec, top_n: int, filters: dict | None = None) -> list[dict]:
    client = get_client()
    res = client.query_points(
        collection_name=config.COLLECTION_NAME,
        query=dense_vec,
        using="dense",
        limit=top_n,
        query_filter=build_filter(filters),
        with_payload=True,
    )
    return [_hit_to_dict(h) for h in res.points]


def sparse_search(indices, values, top_n: int, filters: dict | None = None) -> list[dict]:
    client = get_client()
    res = client.query_points(
        collection_name=config.COLLECTION_NAME,
        query=models.SparseVector(indices=indices, values=values),
        using="sparse",
        limit=top_n,
        query_filter=build_filter(filters),
        with_payload=True,
    )
    return [_hit_to_dict(h) for h in res.points]


def rrf_fuse(
    dense_hits: list[dict],
    sparse_hits: list[dict],
    k: int = config.RRF_K,
    top_n: int | None = None,
) -> list[dict]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank)) across lists."""
    fused: dict[str, dict] = {}

    def _accumulate(hits: list[dict], source: str) -> None:
        for rank, hit in enumerate(hits):
            cid = hit["id"]
            entry = fused.setdefault(
                cid,
                {**hit, "rrf": 0.0, "dense_rank": None, "sparse_rank": None},
            )
            entry["rrf"] += 1.0 / (k + rank + 1)
            entry[f"{source}_rank"] = rank + 1

    _accumulate(dense_hits, "dense")
    _accumulate(sparse_hits, "sparse")

    ordered = sorted(fused.values(), key=lambda e: e["rrf"], reverse=True)
    if top_n:
        ordered = ordered[:top_n]
    return ordered


# --------------------------------------------------------------------------- #
# Browsing (for /chunks)                                                       #
# --------------------------------------------------------------------------- #
def scroll(
    limit: int,
    offset=None,
    filters: dict | None = None,
) -> tuple[list[dict], object]:
    client = get_client()
    records, next_off = client.scroll(
        collection_name=config.COLLECTION_NAME,
        scroll_filter=build_filter(filters),
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )
    out = []
    for r in records:
        payload = r.payload or {}
        out.append({"id": payload.get("chunk_id", str(r.id)), "payload": payload,
                    "text": payload.get("text", "")})
    return out, next_off


def distinct_values(key: str, cap: int = 5000) -> list[str]:
    """Collect the distinct payload values for a key (for filter dropdowns)."""
    values: set[str] = set()
    offset = None
    seen = 0
    while seen < cap:
        recs, offset = scroll(limit=256, offset=offset)
        if not recs:
            break
        for r in recs:
            v = r["payload"].get(key)
            if v:
                values.add(str(v))
        seen += len(recs)
        if offset is None:
            break
    return sorted(values)
