"""Central configuration for the Advanced RAG Explorer.

Every knob is overridable via environment variables (loaded from ``.env``).
The defaults mirror the table in ``src/PROMPT.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Paths                                                                        #
# --------------------------------------------------------------------------- #
APP_DIR = Path(__file__).resolve().parent.parent          # .../Advance_RAG
load_dotenv(APP_DIR / ".env")


def _path(env: str, default: Path) -> Path:
    raw = os.getenv(env, "").strip()
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (APP_DIR / p).resolve()


DATA_DIR = _path("DATA_DIR", APP_DIR / "data")
UPLOAD_DIR = _path("UPLOAD_DIR", APP_DIR / "uploads")
QDRANT_PATH = _path("QDRANT_PATH", APP_DIR / "qdrant_data")

# When set (e.g. http://localhost:6333) we talk to a Qdrant *server* instead of
# the embedded file store. Left blank => embedded, no Docker required.
QDRANT_URL = os.getenv("QDRANT_URL", "").strip()
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "vwo_test_cases")

# --------------------------------------------------------------------------- #
# Groq                                                                         #
# --------------------------------------------------------------------------- #
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

# --------------------------------------------------------------------------- #
# Models                                                                       #
# --------------------------------------------------------------------------- #
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3").strip()
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3").strip()
DENSE_DIM = int(os.getenv("DENSE_DIM", "1024"))
BGE_USE_FP16 = os.getenv("BGE_USE_FP16", "1") == "1"

# ``lite`` mode swaps the heavy transformer models for dependency-free, fully
# local hashing embeddings + a lexical reranker. It is auto-enabled when
# FlagEmbedding is not importable, or forced with RAG_LITE=1. Great for a
# laptop demo; flip to the real models for production-quality retrieval.
FORCE_LITE = os.getenv("RAG_LITE", "").strip() in ("1", "true", "True")

# --------------------------------------------------------------------------- #
# Pipeline tunables (see the README table)                                     #
# --------------------------------------------------------------------------- #
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))       # max chars per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))  # chars repeated
TOP_N_HYBRID = int(os.getenv("TOP_N_HYBRID", "20"))     # candidates per search
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "4"))      # chunks sent to the LLM
RRF_K = int(os.getenv("RRF_K", "60"))                   # RRF smoothing constant
REWRITE_ENABLED = os.getenv("REWRITE_ENABLED", "1") not in ("0", "false", "False")
N_REWRITES = int(os.getenv("N_REWRITES", "3"))
INGEST_BATCH = int(os.getenv("INGEST_BATCH", "32"))

# --------------------------------------------------------------------------- #
# Server                                                                       #
# --------------------------------------------------------------------------- #
PORT = int(os.getenv("PORT", "5050"))
HOST = os.getenv("HOST", "127.0.0.1")

# Default columns used by the ingester / CLI (match the generated CSV).
DEFAULT_TEXT_COLS = ["title", "steps", "expected", "tags"]
DEFAULT_META_COLS = ["id", "jira_id", "priority", "module"]
# Payload keys we expose as UI filters on /chunks.
FILTERABLE_KEYS = ["priority", "module", "jira_id"]
