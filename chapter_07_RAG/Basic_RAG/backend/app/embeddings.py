"""Embeddings via the Nomic Atlas hosted API (nomic-embed-text-v1.5).

`inference_mode="remote"` pins every call to the hosted Atlas API (using
NOMIC_API_KEY) rather than falling back to a local model download.
"""

import time

import nomic
from nomic import embed
from requests.exceptions import ConnectionError as RequestsConnectionError

from app.config import NOMIC_API_KEY, NOMIC_MODEL

_logged_in = False

# DNS resolution for api-atlas.nomic.ai occasionally fails transiently when
# called from inside a worker thread (observed on Windows) even though it
# resolves fine everywhere else. A couple of quick retries absorb that
# without masking a real, persistent connectivity problem.
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 1.5


def _ensure_login() -> None:
    global _logged_in
    if _logged_in:
        return
    if not NOMIC_API_KEY:
        raise RuntimeError(
            "NOMIC_API_KEY is not set. Add it to backend/.env "
            "(get a free key at https://atlas.nomic.ai)."
        )
    nomic.login(NOMIC_API_KEY)
    _logged_in = True


def _embed_with_retry(texts: list[str], task_type: str) -> list[list[float]]:
    _ensure_login()
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            result = embed.text(
                texts=texts,
                model=NOMIC_MODEL,
                task_type=task_type,
                inference_mode="remote",
            )
            return result["embeddings"]
        except RequestsConnectionError as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SECONDS)
    raise last_error


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document/chunk texts (task_type=search_document)."""
    return _embed_with_retry(texts, "search_document")


def embed_query(text: str) -> list[float]:
    """Embed a single query string (task_type=search_query)."""
    return _embed_with_retry([text], "search_query")[0]
