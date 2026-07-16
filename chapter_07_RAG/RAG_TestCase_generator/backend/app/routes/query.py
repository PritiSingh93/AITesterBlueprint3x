from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import config, embeddings, llm, vectorstore

router = APIRouter(prefix="/api", tags=["query"])


MAX_BATCH_COUNT = 30


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None
    module: str | None = None
    count: int | None = None


@router.post("/query")
def run_query(req: QueryRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "question is required")

    if vectorstore.count() == 0:
        raise HTTPException(400, "No documents ingested yet. Run ingestion first.")

    query_vector = embeddings.embed_query(question)
    top_k = req.top_k or config.TOP_K
    retrieved = vectorstore.query(query_vector, top_k=top_k)

    if req.count:
        count = max(1, min(req.count, MAX_BATCH_COUNT))
        module = req.module or question
        answer = llm.generate_test_case_table(module, count, retrieved)
    else:
        answer = llm.generate_answer(question, retrieved)

    return {
        "question": question,
        "answer": answer,
        "model": config.GROQ_MODEL,
        "retrieved_chunks": [
            {
                "id": r["id"],
                "source": r["metadata"]["source"],
                "chunk_index": r["metadata"]["chunk_index"],
                # Chroma's cosine "distance" is 1 - cosine_similarity.
                "similarity": round(1 - r["distance"], 4),
                "text": r["text"],
            }
            for r in retrieved
        ],
    }
