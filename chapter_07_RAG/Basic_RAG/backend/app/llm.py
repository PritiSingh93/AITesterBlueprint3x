"""Answer generation via Groq (openai/gpt-oss-120b)."""

from groq import Groq

from app.config import GROQ_API_KEY, GROQ_MODEL

_client = None

SYSTEM_PROMPT = (
    "You are a helpful assistant answering questions about a document using only "
    "the provided context chunks. Reference which chunk number(s) support your "
    "answer. If the answer is not contained in the context, say you don't know "
    "rather than guessing."
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
        f"Question: {question}\n\n"
        "Answer using only the context above."
    )

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return completion.choices[0].message.content
