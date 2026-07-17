"""Groq-powered query rewriting + grounded generation.

Two LLM touch-points in the pipeline:

1. **Query rewriting** — before retrieval, ask Groq for a few alternate
   phrasings of the user's question. Each phrasing surfaces different
   dense/sparse neighbours, widening recall. Falls back to light heuristic
   rewrites if no API key is configured.

2. **Generation** — after rerank, Groq (``openai/gpt-oss-120b``) writes the
   final answer grounded in the retrieved chunks, with ``[Chunk N]`` citations.
   In *Generate* mode it instead drafts a new structured test case using the
   retrieved rows as templates.
"""

from __future__ import annotations

import json
import re

from . import config

_client = None


def available() -> bool:
    return bool(config.GROQ_API_KEY)


def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def _chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024) -> str:
    client = _get_client()
    completion = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return completion.choices[0].message.content or ""


# --------------------------------------------------------------------------- #
# 1. Query rewriting                                                           #
# --------------------------------------------------------------------------- #
_REWRITE_SYS = (
    "You expand a search query into alternate phrasings for a hybrid retrieval "
    "system over a corpus of software QA test cases (VWO product). Produce "
    "diverse rewrites: one keyword-heavy, one natural-language, one that adds "
    "likely domain synonyms. Return ONLY a JSON array of strings, no prose."
)


def _heuristic_rewrites(question: str, n: int) -> list[str]:
    q = question.strip().rstrip("?")
    variants = [
        q,
        f"test cases for {q}",
        f"{q} steps expected result priority",
        f"how is {q} verified in VWO",
    ]
    # de-dup preserving order
    seen, out = set(), []
    for v in variants:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out[:n]


def rewrite_query(question: str, n: int = config.N_REWRITES) -> list[str]:
    if not config.REWRITE_ENABLED:
        return [question]
    if not available():
        return _heuristic_rewrites(question, n)
    try:
        raw = _chat(
            [
                {"role": "system", "content": _REWRITE_SYS},
                {"role": "user", "content": f"Query: {question}\nReturn {n} rewrites as a JSON array."},
            ],
            temperature=0.4,
            max_tokens=300,
        )
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        arr = json.loads(match.group(0)) if match else []
        rewrites = [str(x).strip() for x in arr if str(x).strip()]
        # Always include the original as the first probe.
        if question not in rewrites:
            rewrites = [question] + rewrites
        return rewrites[:n] or [question]
    except Exception:
        return _heuristic_rewrites(question, n)


# --------------------------------------------------------------------------- #
# 2. Generation                                                                #
# --------------------------------------------------------------------------- #
_ANSWER_SYS = (
    "You answer questions about a set of VWO software test cases using ONLY the "
    "provided context chunks. Cite the chunk numbers that support each claim like "
    "[Chunk 2]. If the answer is not in the context, say you don't know rather "
    "than inventing details. Be concise and concrete."
)

_GENERATE_SYS = (
    "You are a senior QA engineer for VWO (Visual Website Optimizer). Using the "
    "retrieved similar test cases as style/format templates, write ONE new, "
    "high-quality test case for the user's request. Output these labelled "
    "sections exactly: Title, Preconditions, Steps (numbered), Expected Result, "
    "Priority (Critical/High/Medium/Low), Tags (semicolon-separated). Ground the "
    "wording in the retrieved examples and cite which chunks inspired it like "
    "[Chunk 1]."
)


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        p = c.get("payload", {})
        meta = " | ".join(
            f"{k}: {p[k]}" for k in ("id", "jira_id", "module", "priority") if p.get(k)
        )
        parts.append(f"[Chunk {i}{(' | ' + meta) if meta else ''}]\n{c['text']}")
    return "\n\n".join(parts)


def _fallback_answer(question: str, chunks: list[dict]) -> str:
    lines = [
        "_(Groq API key not configured — showing the top retrieved chunks "
        "instead of a generated answer. Set GROQ_API_KEY in .env for full "
        "generation.)_\n",
        f"**Question:** {question}\n",
        "**Most relevant retrieved test cases:**",
    ]
    for i, c in enumerate(chunks, start=1):
        p = c.get("payload", {})
        lines.append(f"- [Chunk {i}] {p.get('jira_id', '')} {p.get('title', c['text'][:80])}")
    return "\n".join(lines)


def generate_answer(question: str, chunks: list[dict], mode: str = "answer") -> str:
    if not available():
        return _fallback_answer(question, chunks)
    context = _build_context(chunks)
    system = _GENERATE_SYS if mode == "generate" else _ANSWER_SYS
    user = (
        f"Retrieved context:\n{context}\n\n"
        f"User request: {question}\n\n"
        + ("Write the new test case now." if mode == "generate"
           else "Answer using only the context above.")
    )
    return _chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3 if mode == "generate" else 0.2,
        max_tokens=1200,
    )


# --------------------------------------------------------------------------- #
# Mode detection                                                               #
# --------------------------------------------------------------------------- #
_GENERATE_TRIGGERS = re.compile(
    r"\b(create|generate|write|draft|make|add|compose)\b.*\b(test case|test|scenario)\b"
    r"|\bnew test case\b|\bwrite a test\b",
    re.IGNORECASE,
)


def detect_mode(question: str) -> str:
    return "generate" if _GENERATE_TRIGGERS.search(question) else "answer"
