"""Advanced RAG Explorer — Flask server.

Two-pane teaching UI over a hybrid (dense + sparse) retrieval pipeline:

    /upload  -> pick a CSV/XLSX + choose text / metadata columns
    /ingest  -> live SSE stage tracker: Read -> Build -> Chunk -> Embed -> Index
    /chunks  -> paginated collection browser with filters
    /chat    -> rewrite -> hybrid search -> RRF -> rerank -> Groq answer

Run:  python app.py   (defaults to http://127.0.0.1:5050)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from rag import config, dataio, groq_client, models, pipeline, qdrant_store

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB uploads

# Single-user demo state (kept in memory; no DB/session needed).
STATE: dict = {"df": None, "path": None, "text_cols": [], "meta_cols": []}


# --------------------------------------------------------------------------- #
# Pages                                                                        #
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("upload.html", active="upload")


@app.route("/upload")
def upload_page():
    return render_template("upload.html", active="upload")


@app.route("/ingest")
def ingest_page():
    return render_template("ingest.html", active="ingest")


@app.route("/chunks")
def chunks_page():
    return render_template("chunks.html", active="chunks")


@app.route("/chat")
def chat_page():
    return render_template("chat.html", active="chat")


# --------------------------------------------------------------------------- #
# Status                                                                       #
# --------------------------------------------------------------------------- #
@app.get("/api/status")
def api_status():
    return jsonify({
        "backend": models.backend_name(),
        "embed_model": models.get_embedder().name if _safe(models.get_embedder) else "unknown",
        "groq": groq_client.available(),
        "groq_model": config.GROQ_MODEL,
        "collection": qdrant_store.collection_info(),
        "tunables": {
            "CHUNK_SIZE": config.CHUNK_SIZE, "CHUNK_OVERLAP": config.CHUNK_OVERLAP,
            "TOP_N_HYBRID": config.TOP_N_HYBRID, "TOP_K_RERANK": config.TOP_K_RERANK,
            "RRF_K": config.RRF_K, "REWRITE_ENABLED": config.REWRITE_ENABLED,
        },
        "has_upload": STATE["df"] is not None,
        "text_cols": STATE["text_cols"],
        "meta_cols": STATE["meta_cols"],
    })


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Upload                                                                       #
# --------------------------------------------------------------------------- #
@app.post("/api/upload")
def api_upload():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        return jsonify({"error": "Only .csv, .xlsx, .xls are supported"}), 400

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.UPLOAD_DIR / f"upload_{int(time.time())}{suffix}"
    file.save(dest)

    try:
        df = dataio.read_table(dest)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Could not read file: {exc}"}), 400

    text_cols, meta_cols = dataio.guess_columns(list(df.columns))
    STATE.update({"df": df, "path": str(dest), "text_cols": text_cols, "meta_cols": meta_cols})

    return jsonify({
        "filename": file.filename,
        "preview": dataio.preview(df),
        "suggested_text_cols": text_cols,
        "suggested_meta_cols": meta_cols,
    })


# --------------------------------------------------------------------------- #
# Ingest (SSE)                                                                 #
# --------------------------------------------------------------------------- #
@app.get("/api/ingest/stream")
def api_ingest_stream():
    if STATE["df"] is None:
        return jsonify({"error": "Upload a file first"}), 400

    text_cols = [c for c in request.args.get("text_cols", "").split(",") if c] or STATE["text_cols"]
    meta_cols = [c for c in request.args.get("meta_cols", "").split(",") if c] or STATE["meta_cols"]
    STATE.update({"text_cols": text_cols, "meta_cols": meta_cols})
    rows = dataio.to_rows(STATE["df"])

    def generate():
        yield _sse({"stage": "start", "status": "running",
                    "data": {"backend": models.backend_name(), "rows": len(rows)}})
        try:
            for event in pipeline.ingest_stream(rows, text_cols, meta_cols):
                yield _sse(event)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"stage": "error", "status": "error", "message": str(exc)})

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# --------------------------------------------------------------------------- #
# Chunks browser                                                               #
# --------------------------------------------------------------------------- #
@app.get("/api/chunks")
def api_chunks():
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, int(request.args.get("page_size", 50)))
    search = request.args.get("q", "").strip().lower()
    filters = {k: request.args.get(k) for k in config.FILTERABLE_KEYS if request.args.get(k)}

    if qdrant_store.count() == 0:
        return jsonify({"total": 0, "page": page, "page_size": page_size,
                        "chunks": [], "last_context": pipeline.LAST_CONTEXT_IDS})

    # Qdrant scroll is cursor-based; walk pages to reach the requested offset,
    # applying an optional substring filter client-side.
    target = page * page_size
    collected: list[dict] = []
    offset = None
    guard = 0
    while len(collected) < target + page_size and guard < 500:
        recs, offset = qdrant_store.scroll(limit=128, offset=offset, filters=filters or None)
        guard += 1
        for r in recs:
            if search and search not in r["text"].lower() and search not in json.dumps(r["payload"]).lower():
                continue
            collected.append(r)
        if offset is None:
            break

    start = (page - 1) * page_size
    window = collected[start:start + page_size]
    return jsonify({
        "total_scanned": len(collected),
        "collection_total": qdrant_store.count(),
        "page": page,
        "page_size": page_size,
        "has_more": offset is not None or len(collected) > start + page_size,
        "chunks": window,
        "last_context": pipeline.LAST_CONTEXT_IDS,
    })


@app.get("/api/chunks/filters")
def api_chunk_filters():
    if qdrant_store.count() == 0:
        return jsonify({k: [] for k in config.FILTERABLE_KEYS})
    return jsonify({k: qdrant_store.distinct_values(k) for k in ("priority", "module")})


# --------------------------------------------------------------------------- #
# Chat                                                                         #
# --------------------------------------------------------------------------- #
@app.post("/api/chat")
def api_chat():
    body = request.get_json(force=True, silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    filters = {k: v for k, v in (body.get("filters") or {}).items() if v}
    try:
        result = pipeline.chat(question, filters or None)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    status = 400 if result.get("error") else 200
    return jsonify(result), status


if __name__ == "__main__":
    print("=" * 66)
    print(" Advanced RAG Explorer")
    print(f"   backend     : {models.backend_name()}  "
          f"({'real bge-m3 + reranker' if models.backend_name() == 'real' else 'lite local fallback'})")
    print(f"   groq        : {'configured' if groq_client.available() else 'NOT set (fallback answers)'}")
    print(f"   qdrant      : {'server ' + config.QDRANT_URL if config.QDRANT_URL else 'embedded ' + str(config.QDRANT_PATH)}")
    print(f"   open        : http://{config.HOST}:{config.PORT}")
    print("=" * 66)
    app.run(host=config.HOST, port=config.PORT, threaded=True, debug=False)
