"""Test case generation via Groq (llama-3.1-8b-instant by default)."""

from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL

_client = None

SYSTEM_PROMPT = (
    "You are a senior QA engineer generating software test cases from "
    "product requirements. Use only the provided context chunks - do not "
    "invent requirements that aren't there. For each test case, output: "
    "a short Title, Preconditions, numbered Steps, and Expected Result. "
    "Cover positive, negative, and edge cases where the context supports "
    "them. Reference which chunk number(s) each test case is based on. "
    "If the context doesn't contain enough information to generate "
    "meaningful test cases, say so rather than guessing."
)


def get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to backend/.env "
                "(get a free key at https://console.groq.com/keys)."
            )
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        source = c["metadata"]["source"]
        parts.append(f"[Chunk {i + 1} | source: {source}]\n{c['text']}")
    return "\n\n".join(parts)


def generate_answer(question: str, chunks: list[dict]) -> str:
    client = get_client()
    context = _build_context(chunks)
    user_prompt = (
        f"Context:\n{context}\n\n"
        f"User request: {question}\n\n"
        "Generate the test cases using only the context above."
    )

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=2048,
    )
    return completion.choices[0].message.content
