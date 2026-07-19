"""Shared configuration for QABuddyAI (ingest + backend + eval).

Every knob is overridable via environment variables, loaded from `.env` at the
chapter root. Defaults assume the docker-compose stack; for local dev point
QDRANT_URL / TEI_* at wherever those services run.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]  # .../chapter_08_QABuddy_AI
load_dotenv(ROOT / ".env")


def _path(env: str, default: Path) -> Path:
    raw = os.getenv(env, "").strip()
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (ROOT / p).resolve()


DATA_ROOT = _path("DATA_ROOT", ROOT / "QABuddyAI_Data_Sources")
STATE_DIR = _path("STATE_DIR", ROOT / "ingest" / ".state")
GENERATION_PROMPT_FILE = _path(
    "GENERATION_PROMPT_FILE", ROOT / "QABuddyAI_Generation_Prompt.md"
)

# --------------------------------------------------------------------------- #
# Services                                                                     #
# --------------------------------------------------------------------------- #
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip()
COLLECTION = os.getenv("COLLECTION", "qabuddy")

TEI_EMBED_URL = os.getenv("TEI_EMBED_URL", "http://localhost:8080").rstrip("/")
TEI_RERANK_URL = os.getenv("TEI_RERANK_URL", "http://localhost:8081").rstrip("/")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

# Sparse side of the hybrid. TEI does not expose BGE-M3's learned sparse head,
# so the default is BM25 via fastembed (pairs with Qdrant's IDF modifier —
# the standard Qdrant hybrid recipe). Set SPARSE_BACKEND=tei and point
# TEI_SPARSE_URL at a TEI instance serving a SPLADE model to use /embed_sparse.
SPARSE_BACKEND = os.getenv("SPARSE_BACKEND", "bm25").strip()
TEI_SPARSE_URL = os.getenv("TEI_SPARSE_URL", TEI_EMBED_URL).rstrip("/")

DENSE_DIM = int(os.getenv("DENSE_DIM", "1024"))  # BGE-M3

# --------------------------------------------------------------------------- #
# Pipeline knobs                                                               #
# --------------------------------------------------------------------------- #
TOP_N_HYBRID = int(os.getenv("TOP_N_HYBRID", "20"))   # candidates per hybrid leg
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", "8"))    # chunks sent to the LLM
INGEST_BATCH = int(os.getenv("INGEST_BATCH", "32"))

# --------------------------------------------------------------------------- #
# JIRA via MCP                                                                 #
# --------------------------------------------------------------------------- #
JIRA_MCP_URL = os.getenv("JIRA_MCP_URL", "").strip()
JIRA_MCP_TOKEN = os.getenv("JIRA_MCP_TOKEN", "").strip()
JIRA_MCP_SEARCH_TOOL = os.getenv("JIRA_MCP_SEARCH_TOOL", "searchJiraIssuesUsingJql")
JQL_FILE = _path("JQL_FILE", ROOT / "config" / "jql.txt")

# --------------------------------------------------------------------------- #
# Data source registry: cli key -> (folder, source_type)                       #
# --------------------------------------------------------------------------- #
SOURCES: dict[str, tuple[str, str]] = {
    "selenium":   ("01_Selenium_Framework_Repo", "selenium_code"),
    "playwright": ("02_Playwright_Framework_Repo", "playwright_code"),
    "testcases":  ("03_TestCases_CSV_XLSX", "test_case"),
    "jira":       ("04_JIRA_Tickets", "jira"),
    "docs":       ("05_Company_Docs_PDF_MD", "doc"),
    "figma":      ("06_Figma_Design_Phase2", "design"),
    "meetings":   ("07_Meeting_Notes_Transcripts", "meeting"),
    "lucid":      ("08_LucidChart_Exports", "diagram"),
    "prd":        ("09_PRD_SRS_BRD_FRD", "prd"),
    "jenkins":    ("10_Jenkins_Logs_Results", "jenkins"),
}
PHASE2_SOURCES = {"figma"}  # scaffolded but skipped by ingesters in phase 1

# Keyword payload fields that get a Qdrant index (filtered retrieval + UI).
INDEXED_PAYLOAD_KEYS = [
    "source_type", "module", "priority", "jira_id", "tc_id", "doc_kind",
    "repo_name", "job_name", "status",
]
