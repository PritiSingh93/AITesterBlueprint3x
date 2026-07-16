"""Embeddings via the Mistral AI hosted API (mistral-embed)."""

from mistralai.client import Mistral

from app.config import MISTRAL_API_KEY, MISTRAL_MODEL

_client = None


def _get_client() -> Mistral:
    global _client
    if _client is None:
        if not MISTRAL_API_KEY:
            raise RuntimeError(
                "MISTRAL_API_KEY is not set. Add it to backend/.env "
                "(get a free key at https://console.mistral.ai/api-keys)."
            )
        _client = Mistral(api_key=MISTRAL_API_KEY)
    return _client


def _embed(texts: list[str]) -> list[list[float]]:
    client = _get_client()
    response = client.embeddings.create(model=MISTRAL_MODEL, inputs=texts)
    return [item.embedding for item in response.data]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document/chunk texts."""
    return _embed(texts)


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return _embed([text])[0]
