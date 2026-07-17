"""End-to-end pipeline orchestration.

* ``chunk_document``  — 1 row = 1 chunk when small, else overlapping splits.
* ``ingest_stream``   — a generator that yields stage events (Read -> Build
  docs -> Chunk -> Embed -> Index) so the UI can render a live tracker.
* ``chat``            — runs rewrite -> hybrid search -> RRF -> rerank ->
  generate and returns the full trace for the UI to visualise.
"""

from __future__ import annotations

import time

from . import config, groq_client, models, qdrant_store

# Chunk ids used to build the most recent chat answer (for /chunks highlight).
LAST_CONTEXT_IDS: list[str] = []


# --------------------------------------------------------------------------- #
# Chunking                                                                     #
# --------------------------------------------------------------------------- #
def chunk_document(
    text: str,
    size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    chunks = []
    for i in range(0, len(text), step):
        piece = text[i:i + size].strip()
        if piece:
            chunks.append(piece)
        if i + size >= len(text):
            break
    return chunks


def assemble_document(row: dict, text_cols: list[str]) -> str:
    parts = []
    for col in text_cols:
        val = row.get(col)
        if val is None or str(val).strip() == "" or str(val).lower() == "nan":
            continue
        parts.append(f"{col}: {str(val).strip()}")
    return "\n".join(parts)


def _overlap_prefix_len(prev: str, cur: str, max_overlap: int) -> int:
    """How many leading chars of ``cur`` are repeated from the tail of ``prev``."""
    for n in range(min(max_overlap, len(prev), len(cur)), 0, -1):
        if prev[-n:] == cur[:n]:
            return n
    return 0


def build_chunks(rows: list[dict], text_cols: list[str], meta_cols: list[str]) -> list[dict]:
    chunks: list[dict] = []
    for r_idx, row in enumerate(rows):
        doc = assemble_document(row, text_cols)
        pieces = chunk_document(doc)
        source = str(row.get("id") or row.get("jira_id") or f"row-{r_idx + 1}")
        for c_idx, piece in enumerate(pieces):
            payload = {
                "chunk_id": f"{source}::{c_idx}",
                "source": source,
                "chunk_index": c_idx,
                "n_chunks": len(pieces),
                "text": piece,
                "title": str(row.get("title", "") or ""),
            }
            for m in meta_cols:
                if m in row and str(row.get(m)).lower() != "nan":
                    payload[m] = str(row.get(m))
            chunks.append({"id": payload["chunk_id"], "text": piece, "payload": payload})
    return chunks


def chunk_stats(chunks: list[dict]) -> dict:
    lengths = [len(c["text"]) for c in chunks] or [0]
    n_buckets = 8
    lo, hi = min(lengths), max(lengths)
    span = max(1, hi - lo)
    buckets = [0] * n_buckets
    for L in lengths:
        b = min(n_buckets - 1, int((L - lo) / span * n_buckets))
        buckets[b] += 1
    edges = [round(lo + span * i / n_buckets) for i in range(n_buckets + 1)]
    # First few sample chunks, with detected overlap length vs the previous one.
    samples = []
    for i, c in enumerate(chunks[:4]):
        prev = chunks[i - 1]["text"] if i > 0 and chunks[i - 1]["payload"]["source"] == c["payload"]["source"] else ""
        ov = _overlap_prefix_len(prev, c["text"], config.CHUNK_OVERLAP) if prev else 0
        samples.append({
            "id": c["id"],
            "overlap": ov,
            "text": c["text"][:600],
        })
    return {
        "total": len(chunks),
        "avg": round(sum(lengths) / len(lengths)),
        "min": lo,
        "max": hi,
        "histogram": {"buckets": buckets, "edges": edges},
        "samples": samples,
    }


# --------------------------------------------------------------------------- #
# Ingestion (streaming)                                                        #
# --------------------------------------------------------------------------- #
def ingest_stream(rows: list[dict], text_cols: list[str], meta_cols: list[str]):
    """Yield stage events; the last event of each stage carries its ``data``."""
    t0 = time.time()

    yield {"stage": "read", "status": "running", "message": "Reading rows…"}
    yield {"stage": "read", "status": "done",
           "data": {"rows": len(rows), "text_cols": text_cols, "meta_cols": meta_cols}}

    yield {"stage": "build", "status": "running", "message": "Assembling documents…"}
    chunks = build_chunks(rows, text_cols, meta_cols)
    yield {"stage": "build", "status": "done",
           "data": {"documents": len(rows), "sample": assemble_document(rows[0], text_cols)[:500] if rows else ""}}

    yield {"stage": "chunk", "status": "running", "message": "Chunking…"}
    yield {"stage": "chunk", "status": "done", "data": chunk_stats(chunks)}

    # Embed in batches with progress + a preview from the first chunk.
    yield {"stage": "embed", "status": "running", "message": f"Embedding with {models.get_embedder().name}…",
           "data": {"backend": models.backend_name(), "model": models.get_embedder().name}}
    embedded: list[dict] = []
    total = len(chunks)
    batch = config.INGEST_BATCH
    preview = None
    for start in range(0, total, batch):
        part = chunks[start:start + batch]
        vecs = models.embed_documents([c["text"] for c in part])
        for c, v in zip(part, vecs):
            embedded.append({**c, **v})
        if preview is None and vecs:
            preview = {
                "dense_preview": [round(x, 4) for x in vecs[0]["dense"][:8]],
                "dense_dim": len(vecs[0]["dense"]),
                "sparse_top": [[t, round(w, 4)] for t, w in vecs[0]["sparse_top"][:5]],
            }
        yield {"stage": "embed", "status": "progress",
               "data": {"done": min(start + batch, total), "total": total, **(preview or {})}}
    yield {"stage": "embed", "status": "done",
           "data": {"total": total, **(preview or {})}}

    # Index into Qdrant.
    yield {"stage": "index", "status": "running", "message": "Creating collection + upserting…"}
    dim = len(embedded[0]["dense"]) if embedded else config.DENSE_DIM
    qdrant_store.recreate_collection(dim)
    for start in range(0, total, 128):
        qdrant_store.upsert(embedded[start:start + 128])
        yield {"stage": "index", "status": "progress",
               "data": {"done": min(start + 128, total), "total": total}}
    info = qdrant_store.collection_info()
    yield {"stage": "index", "status": "done",
           "data": {"collection": info, "elapsed": round(time.time() - t0, 1)}}

    yield {"stage": "complete", "status": "done",
           "data": {"chunks": total, "elapsed": round(time.time() - t0, 1)}}


def ingest_sync(rows: list[dict], text_cols: list[str], meta_cols: list[str]) -> dict:
    """Non-streaming ingest (used by the CLI). Returns a summary dict."""
    last = {}
    for event in ingest_stream(rows, text_cols, meta_cols):
        last = event
        if event["stage"] in ("chunk", "index", "complete") and event["status"] == "done":
            data = event.get("data", {})
            if event["stage"] == "chunk":
                print(f"  chunked  : {data['total']} chunks "
                      f"(avg {data['avg']} / min {data['min']} / max {data['max']} chars)")
            elif event["stage"] == "index":
                print(f"  indexed  : {data['collection'].get('points')} points into "
                      f"'{data['collection'].get('name')}'")
            elif event["stage"] == "complete":
                print(f"  done in {data['elapsed']}s")
        elif event["stage"] == "read" and event["status"] == "done":
            print(f"  read     : {event['data']['rows']} rows")
    return last.get("data", {})


# --------------------------------------------------------------------------- #
# Chat (retrieval + generation)                                               #
# --------------------------------------------------------------------------- #
def _pool(hit_lists: list[list[dict]], top_n: int) -> list[dict]:
    """Merge per-rewrite hit lists, keeping the best score per chunk id."""
    best: dict[str, dict] = {}
    for hits in hit_lists:
        for h in hits:
            cur = best.get(h["id"])
            if cur is None or h["score"] > cur["score"]:
                best[h["id"]] = h
    ordered = sorted(best.values(), key=lambda h: h["score"], reverse=True)
    return ordered[:top_n]


def chat(question: str, filters: dict | None = None) -> dict:
    global LAST_CONTEXT_IDS
    trace: dict = {"question": question, "backend": models.backend_name(),
                   "groq": groq_client.available()}
    t0 = time.time()

    if qdrant_store.count() == 0:
        return {**trace, "error": "No data ingested yet. Upload + ingest a CSV first."}

    mode = groq_client.detect_mode(question)
    trace["mode"] = mode

    # 1. Rewrite
    rewrites = groq_client.rewrite_query(question)
    trace["rewrites"] = rewrites

    # 2. Hybrid search across every rewrite, then pool.
    dense_lists, sparse_lists = [], []
    for rw in rewrites:
        qv = models.embed_query(rw)
        dense_lists.append(qdrant_store.dense_search(qv["dense"], config.TOP_N_HYBRID, filters))
        sparse_lists.append(
            qdrant_store.sparse_search(qv["sparse_indices"], qv["sparse_values"],
                                       config.TOP_N_HYBRID, filters)
        )
    dense_top = _pool(dense_lists, config.TOP_N_HYBRID)
    sparse_top = _pool(sparse_lists, config.TOP_N_HYBRID)
    trace["dense_top"] = _slim(dense_top, 10)
    trace["sparse_top"] = _slim(sparse_top, 10)

    # 3. RRF fusion
    fused = qdrant_store.rrf_fuse(dense_top, sparse_top, config.RRF_K, config.TOP_N_HYBRID)
    trace["fused_top"] = _slim(fused, 10)

    # 4. Cross-encoder rerank of the fused candidates.
    candidates = fused[: max(config.TOP_N_HYBRID, config.TOP_K_RERANK)]
    scores = models.rerank_scores(question, [c["text"] for c in candidates])
    for c, s in zip(candidates, scores):
        c["rerank"] = s
    reranked = sorted(candidates, key=lambda c: c["rerank"], reverse=True)
    top_k = reranked[: config.TOP_K_RERANK]
    trace["rerank"] = {
        "before": [{"id": c["id"], "rrf": round(c.get("rrf", 0), 5),
                    "title": c["payload"].get("title", "")} for c in candidates[:10]],
        "after": [{"id": c["id"], "score": c["rerank"],
                   "title": c["payload"].get("title", "")} for c in reranked[:10]],
    }
    trace["context"] = [
        {"id": c["id"], "score": c["rerank"], "text": c["text"], "payload": c["payload"]}
        for c in top_k
    ]

    # 5. Generate
    answer = groq_client.generate_answer(question, top_k, mode=mode)
    trace["answer"] = answer
    trace["elapsed"] = round(time.time() - t0, 2)

    LAST_CONTEXT_IDS = [c["id"] for c in top_k]
    return trace


def _slim(hits: list[dict], n: int) -> list[dict]:
    out = []
    for h in hits[:n]:
        out.append({
            "id": h["id"],
            "score": round(h.get("score", 0), 4),
            "rrf": round(h["rrf"], 5) if "rrf" in h else None,
            "dense_rank": h.get("dense_rank"),
            "sparse_rank": h.get("sparse_rank"),
            "title": h["payload"].get("title", "") if h.get("payload") else "",
            "jira_id": h["payload"].get("jira_id", "") if h.get("payload") else "",
        })
    return out
