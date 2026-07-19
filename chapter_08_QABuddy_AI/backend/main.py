"""QABuddyAI API: POST /ask (question in, cited answer out) + GET /health.

Run locally:  uvicorn backend.main:app --reload --port 8000
In Docker:    see docker-compose.yml (service: backend)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.generate import answer as generate_answer  # noqa: E402
from backend.retrieval import retrieve, source_label  # noqa: E402
from common import config  # noqa: E402
from ingest.embed_and_upsert import get_client  # noqa: E402

app = FastAPI(title="QABuddyAI", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # internal tool behind nginx/VPN
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    filters: Optional[Dict] = None  # e.g. {"source_type": ["jira"], "module": "checkout"}
    top_k: Optional[int] = Field(default=None, ge=1, le=20)


NOT_FOUND_ANSWER = (
    "Not found in the knowledge base — retrieval returned no matching chunks. "
    "Check that the relevant data-source folder (01-10) has been populated "
    "and ingested (`python ingest/run_full_ingest.py --source all`)."
)


@app.post("/ask")
def ask(req: AskRequest) -> Dict:
    try:
        chunks = retrieve(req.question, filters=req.filters, top_k=req.top_k)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"retrieval failed: {exc}")

    if not chunks:
        return {"answer": NOT_FOUND_ANSWER, "citations": [], "sources": []}

    try:
        result = generate_answer(req.question, chunks)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"generation failed: {exc}")

    sources: List[Dict] = []
    for i, chunk in enumerate(chunks, 1):
        p = chunk["payload"]
        sources.append(
            {
                "n": i,
                "source": source_label(p),
                "source_type": p.get("source_type", "?"),
                "score": round(chunk["score"], 4),
                "file_path": p.get("file_path", ""),
                "jira_id": p.get("jira_id", ""),
                "tc_id": p.get("tc_id", ""),
                "module": p.get("module", ""),
                "text": p.get("text", ""),
            }
        )
    return {"answer": result["answer"], "citations": result["citations"], "sources": sources}


@app.get("/health")
def health() -> Dict:
    status: Dict[str, str] = {}
    try:
        info = get_client().get_collection(config.COLLECTION)
        status["qdrant"] = f"ok ({info.points_count} points)"
    except Exception as exc:
        status["qdrant"] = f"error: {exc}"
    for name, url in (("tei_embed", config.TEI_EMBED_URL),
                      ("tei_rerank", config.TEI_RERANK_URL)):
        try:
            httpx.get(f"{url}/health", timeout=5).raise_for_status()
            status[name] = "ok"
        except Exception as exc:
            status[name] = f"error: {exc}"
    status["groq"] = "ok (key set)" if config.GROQ_API_KEY else "error: GROQ_API_KEY missing"
    healthy = all(v.startswith("ok") for v in status.values())
    return {"healthy": healthy, "services": status}
