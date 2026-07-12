import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def _resolve_path(value: str, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


DATA_DIR = _resolve_path(os.getenv("DATA_DIR", ""), (PROJECT_DIR / "data").resolve())
CHROMA_DIR = _resolve_path(os.getenv("CHROMA_DIR", ""), (BACKEND_DIR / "chroma_db").resolve())
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "rag_explorer_docs")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

NOMIC_API_KEY = os.getenv("NOMIC_API_KEY", "")
NOMIC_MODEL = os.getenv("NOMIC_MODEL", "nomic-embed-text-v1.5")

# Chunking targets are expressed in characters and converted to an
# approximate token count using the common ~4-chars-per-token heuristic.
# This keeps chunk sizing transparent and dependency-free (no tokenizer
# download required) while still landing in the requested 500-1000 token range.
CHUNK_TARGET_CHARS = int(os.getenv("CHUNK_TARGET_CHARS", "3200"))
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "400"))

TOP_K = int(os.getenv("TOP_K", "4"))

PORT = int(os.getenv("PORT", "8000"))

# OCR fallback (used only when a PDF has no extractable text layer, e.g.
# design-tool exports that outline text as vector paths). Optional: only
# needed if Tesseract/Poppler aren't already on PATH.
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
OCR_DPI = int(os.getenv("OCR_DPI", "200"))
