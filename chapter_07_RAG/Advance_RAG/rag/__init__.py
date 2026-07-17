"""Advanced RAG Explorer — hybrid retrieval + rerank + Groq generation.

Package layout
--------------
config        : tunables (chunking, retrieval, models, paths) read from .env
models        : lazy loaders for bge-m3 (dense+sparse) and bge-reranker-v2-m3,
                each with a dependency-free "lite" fallback so the demo runs
                even without the ~3 GB model download.
qdrant_store  : embedded Qdrant collection with named dense + sparse vectors,
                filtered search, and Reciprocal Rank Fusion.
groq_client   : query rewriting + grounded answer / test-case generation.
pipeline      : ingest and chat orchestration that emit stage events for the UI.
"""

__all__ = ["config", "models", "qdrant_store", "groq_client", "pipeline"]
