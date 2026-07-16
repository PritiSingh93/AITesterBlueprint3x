"""Local ChromaDB persistent vector store."""

import chromadb

from app.config import CHROMA_DIR, COLLECTION_NAME

_client = None


def get_client():
    global _client
    if _client is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def get_collection():
    client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return get_collection()


def add_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    collection = get_collection()
    collection.upsert(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=[c["text"] for c in chunks],
        metadatas=[
            {"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks
        ],
    )


def count() -> int:
    return get_collection().count()


def query(query_embedding: list[float], top_k: int = 10) -> list[dict]:
    collection = get_collection()
    total = collection.count()
    if total == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, total),
    )

    out = []
    for i in range(len(results["ids"][0])):
        out.append(
            {
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
        )
    return out
