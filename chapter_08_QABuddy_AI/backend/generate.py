"""Answer generation: fills the runtime template from
QABuddyAI_Generation_Prompt.md with retrieved context, calls Groq, and
extracts the citations actually used.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from groq import Groq

from common import config
from backend.retrieval import source_label

_FENCE_RE = re.compile(r"```\s*\n(.*?)```", re.S)
_CITATION_RE = re.compile(r"\[source:\s*([^\]]+)\]", re.I)

_template: Optional[str] = None


def load_template() -> str:
    """The fenced block of the generation prompt file, used verbatim."""
    global _template
    if _template is None:
        text = config.GENERATION_PROMPT_FILE.read_text(encoding="utf-8-sig")
        m = _FENCE_RE.search(text)
        _template = (m.group(1) if m else text).strip()
    return _template


def format_context(chunks: List[Dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        p = chunk["payload"]
        parts.append(
            f"[{i}] source: {source_label(p)} ({p.get('source_type', '?')})\n"
            f"{p.get('text', '')}"
        )
    return "\n\n---\n\n".join(parts)


def answer(question: str, chunks: List[Dict]) -> Dict:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set (see .env.example)")
    # .replace, not .format — retrieved code chunks are full of braces.
    prompt = (
        load_template()
        .replace("{context}", format_context(chunks))
        .replace("{question}", question)
    )
    client = Groq(api_key=config.GROQ_API_KEY)
    resp = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1500,
    )
    text = resp.choices[0].message.content or ""
    citations = list(dict.fromkeys(m.strip() for m in _CITATION_RE.findall(text)))
    return {"answer": text, "citations": citations}
