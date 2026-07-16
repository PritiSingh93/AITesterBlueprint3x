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
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "langflow_ai3x_TC")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-embed")

# Chunking targets, in characters - matches the Langflow SplitText node
# (chunk_size=1000, chunk_overlap=200) this app was ported from.
CHUNK_TARGET_CHARS = int(os.getenv("CHUNK_TARGET_CHARS", "1000"))
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "200"))

# Matches the Langflow Chroma node's number_of_results.
TOP_K = int(os.getenv("TOP_K", "10"))

PORT = int(os.getenv("PORT", "8000"))
