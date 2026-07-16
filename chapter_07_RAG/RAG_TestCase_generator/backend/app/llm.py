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


TABLE_SYSTEM_PROMPT = (
    "You are a senior QA engineer generating software test cases from "
    "product requirements. Use only the provided context chunks - do not "
    "invent requirements that aren't there. "
    "Output ONLY a markdown table, nothing before or after it, with exactly "
    "this header row: "
    "| TC ID | Module | Type | Title | Preconditions | Steps | Expected Result |\n"
    "Generate exactly the requested number of rows. Distribute Type across "
    "a mix of Positive, Negative, and Edge cases. Keep every cell on a "
    "single line with no literal line breaks - separate steps within the "
    "Steps cell using '; '. TC IDs must be sequential and must start at the "
    "number given in the user prompt (e.g. TC-021, TC-022, ...). "
    "If the context doesn't contain enough information to justify the "
    "requested number of distinct test cases, generate as many genuinely "
    "distinct ones as the context supports rather than inventing filler."
)


def generate_test_case_table(
    module: str,
    count: int,
    chunks: list[dict],
    start_index: int = 1,
    exclude_titles: list[str] | None = None,
) -> str:
    """Generates `count` test case rows as a markdown table for one module,
    grounded only in the retrieved chunks. Used by the batch generator.

    Repeated calls for the same module retrieve the same chunks (retrieval
    is deterministic), so `start_index` keeps TC IDs sequential across
    calls and `exclude_titles` steers the model away from repeating
    scenarios it already generated in earlier calls for this module.
    """
    client = get_client()
    context = _build_context(chunks)
    end_index = start_index + count - 1
    user_prompt = (
        f"Context:\n{context}\n\n"
        f"Module: {module}\n"
        f"Generate exactly {count} test cases for this module using only "
        "the context above. "
        f"Number the TC IDs sequentially starting at TC-{start_index:03d} "
        f"through TC-{end_index:03d}."
    )
    if exclude_titles:
        already = "\n".join(f"- {t}" for t in exclude_titles)
        user_prompt += (
            "\n\nThese test case titles were already generated in earlier "
            "batches for this module - do not repeat them or generate close "
            f"rephrasings of them; cover new, distinct scenarios instead:\n{already}"
        )
    max_tokens = min(8000, 180 * count + 300)

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": TABLE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return completion.choices[0].message.content
