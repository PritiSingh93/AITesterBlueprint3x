"""Embedding Explorer endpoints: raw vectors, pairwise similarity, and a
2D PCA projection of a small word set for visualization."""

import numpy as np
from fastapi import APIRouter
from pydantic import BaseModel

from app import embeddings

router = APIRouter(prefix="/api/embeddings", tags=["embedding-explorer"])

DEFAULT_WORDS = [
    "king",
    "queen",
    "man",
    "woman",
    "prince",
    "princess",
    "apple",
    "orange",
    "car",
    "truck",
]


class VectorRequest(BaseModel):
    text: str


class CompareRequest(BaseModel):
    text_a: str
    text_b: str


class ProjectRequest(BaseModel):
    words: list[str] | None = None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


@router.post("/vector")
def get_vector(req: VectorRequest):
    vector = embeddings.embed_query(req.text)
    return {
        "text": req.text,
        "dimensions": len(vector),
        "vector_preview": vector[:24],
    }


@router.post("/compare")
def compare(req: CompareRequest):
    vectors = embeddings.embed_documents([req.text_a, req.text_b])
    similarity = _cosine_similarity(vectors[0], vectors[1])
    return {
        "text_a": req.text_a,
        "text_b": req.text_b,
        "cosine_similarity": round(similarity, 4),
    }


@router.post("/project")
def project(req: ProjectRequest):
    words = req.words or DEFAULT_WORDS
    vectors = np.array(embeddings.embed_documents(words))

    # 2D projection via PCA (SVD on the centered matrix) - no sklearn
    # dependency needed for a simple visualization.
    centered = vectors - vectors.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    coords = centered @ vt[:2].T

    return {
        "points": [
            {
                "word": word,
                "x": round(float(coords[i][0]), 4),
                "y": round(float(coords[i][1]), 4),
            }
            for i, word in enumerate(words)
        ]
    }
