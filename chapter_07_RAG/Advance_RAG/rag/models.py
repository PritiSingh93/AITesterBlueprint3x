"""Embedding + re-ranking models.

Two implementations sit behind one small interface:

* **Real** — ``bge-m3`` (dense + sparse in a single forward pass) and the
  ``bge-reranker-v2-m3`` cross-encoder, both via FlagEmbedding. This is the
  path the README/PROMPT describes and what you want for real retrieval
  quality. First use downloads ~2.3 GB (bge-m3) + ~570 MB (reranker).

* **Lite** — a dependency-free, fully local fallback: hashing-based dense +
  sparse vectors and a lexical-overlap reranker. Auto-selected when
  FlagEmbedding is unavailable, or forced with ``RAG_LITE=1``. It lets the
  whole app + UI run on any laptop with no model download, which is perfect
  for the teaching demo — the *shape* of every stage (dense vec, sparse
  tokens, rerank reorder) is identical, only the numbers are simpler.

Every embed call returns dicts shaped like::

    {
        "dense":         [float, ...],          # length = DENSE_DIM
        "sparse_indices":[int, ...],            # u32 token ids
        "sparse_values": [float, ...],          # matching weights
        "sparse_top":    [(term, weight), ...], # human-readable, for the UI
    }
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from functools import lru_cache

from . import config

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_lock = threading.Lock()


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# --------------------------------------------------------------------------- #
# Backend selection                                                            #
# --------------------------------------------------------------------------- #
def _flagembedding_available() -> bool:
    if config.FORCE_LITE:
        return False
    try:
        import FlagEmbedding  # noqa: F401
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def backend_name() -> str:
    return "real" if _flagembedding_available() else "lite"


# ======================================================================= #
#  Embedder                                                               #
# ======================================================================= #
class _LiteEmbedder:
    """Hashing dense vectors + token-frequency sparse vectors (no downloads)."""

    dim = config.DENSE_DIM
    name = "lite-hash-embed"

    def _dense(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        toks = tokenize(text)
        # Character 3-grams + word tokens hashed into the dense space give a
        # surprisingly usable similarity signal for a zero-dependency demo.
        grams = toks + [text[i:i + 3] for i in range(0, max(0, len(text) - 2), 2)]
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 17) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def _sparse(self, text: str):
        toks = tokenize(text)
        counts: dict[str, int] = {}
        for t in toks:
            counts[t] = counts.get(t, 0) + 1
        total = sum(counts.values()) or 1
        indices, values, top = [], [], []
        for term, c in counts.items():
            idx = int(hashlib.md5(term.encode()).hexdigest(), 16) % (2 ** 31)
            # tf * a light idf-ish length damp — enough to rank lexical hits.
            weight = (c / total) * (1.0 + math.log(1 + len(term)))
            indices.append(idx)
            values.append(round(weight, 6))
            top.append((term, weight))
        top.sort(key=lambda x: x[1], reverse=True)
        return indices, values, top[:8]

    def embed(self, texts: list[str]) -> list[dict]:
        out = []
        for t in texts:
            si, sv, stop = self._sparse(t)
            out.append({
                "dense": self._dense(t),
                "sparse_indices": si,
                "sparse_values": sv,
                "sparse_top": stop,
            })
        return out


class _BGEM3Embedder:
    """Real bge-m3: dense + sparse (lexical) weights in one pass."""

    name = "BAAI/bge-m3"

    def __init__(self) -> None:
        from FlagEmbedding import BGEM3FlagModel
        self._model = BGEM3FlagModel(config.EMBED_MODEL, use_fp16=config.BGE_USE_FP16)
        self.dim = config.DENSE_DIM

    def embed(self, texts: list[str]) -> list[dict]:
        res = self._model.encode(
            texts,
            batch_size=config.INGEST_BATCH,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = res["dense_vecs"]
        lexical = res["lexical_weights"]
        tok = self._model.tokenizer
        out = []
        for i, text in enumerate(texts):
            weights: dict = lexical[i]
            indices, values, top = [], [], []
            for tid, w in weights.items():
                w = float(w)
                if w <= 0:
                    continue
                indices.append(int(tid))
                values.append(round(w, 6))
                term = tok.decode([int(tid)]).strip() or f"<{tid}>"
                top.append((term, w))
            top.sort(key=lambda x: x[1], reverse=True)
            out.append({
                "dense": [float(x) for x in dense[i]],
                "sparse_indices": indices,
                "sparse_values": values,
                "sparse_top": top[:8],
            })
        return out


_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                _embedder = (_BGEM3Embedder() if backend_name() == "real"
                             else _LiteEmbedder())
    return _embedder


def embed_documents(texts: list[str]) -> list[dict]:
    return get_embedder().embed(texts)


def embed_query(text: str) -> dict:
    return get_embedder().embed([text])[0]


# ======================================================================= #
#  Re-ranker (cross-encoder)                                              #
# ======================================================================= #
class _LiteReranker:
    name = "lite-lexical-rerank"

    def score(self, query: str, passages: list[str]) -> list[float]:
        q = set(tokenize(query))
        if not q:
            return [0.0] * len(passages)
        scores = []
        for p in passages:
            p_toks = tokenize(p)
            p_set = set(p_toks)
            overlap = len(q & p_set)
            # Jaccard-ish overlap + coverage of the query terms, scaled to a
            # logit-like range so the display resembles a cross-encoder score.
            coverage = overlap / len(q)
            density = overlap / (len(p_set) or 1)
            scores.append(round(4.0 * coverage + 1.5 * density - 2.0, 4))
        return scores


class _BGEReranker:
    name = "BAAI/bge-reranker-v2-m3"

    def __init__(self) -> None:
        from FlagEmbedding import FlagReranker
        self._model = FlagReranker(config.RERANK_MODEL, use_fp16=config.BGE_USE_FP16)

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        pairs = [[query, p] for p in passages]
        raw = self._model.compute_score(pairs, normalize=False)
        if isinstance(raw, (int, float)):
            raw = [raw]
        return [round(float(s), 4) for s in raw]


_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                _reranker = (_BGEReranker() if backend_name() == "real"
                             else _LiteReranker())
    return _reranker


def rerank_scores(query: str, passages: list[str]) -> list[float]:
    return get_reranker().score(query, passages)
