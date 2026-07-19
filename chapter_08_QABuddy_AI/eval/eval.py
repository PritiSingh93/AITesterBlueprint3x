"""Evaluation harness for QABuddyAI.

Golden set: eval/golden_set.jsonl — one JSON object per line:
    {"question": "...",
     "expected_sources": ["PROJ-123", "TC-1042", "pages/LoginPage.java"],
     "reference_answer": "optional one-liner"}

Metrics:
  hit-rate@k            expected source found in the top-k retrieved chunks
  citation correctness  (--judge) do the answer's citations point at chunks
                        that actually support the claims? (LLM judge, 0-1)
  faithfulness          (--judge) is every claim grounded in the retrieved
                        context, nothing invented? (LLM judge, 0-1)

Usage:
    python eval/eval.py                 # retrieval-only (fast, no LLM cost)
    python eval/eval.py --judge         # + generation + LLM-judge metrics
    python eval/eval.py --k 8
Run after every chunking/tuning change — tune with numbers, not vibes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.retrieval import retrieve, source_label  # noqa: E402
from common import config  # noqa: E402

GOLDEN_SET = Path(__file__).parent / "golden_set.jsonl"

JUDGE_PROMPT = """You are grading a RAG answer for a QA-engineering assistant.

QUESTION:
{question}

RETRIEVED CONTEXT:
{context}

ANSWER:
{answer}

Grade strictly and reply with ONLY this JSON:
{{"citation_correctness": <0.0-1.0: do the [source: ...] citations point at
context chunks that actually support the cited claims?>,
"faithfulness": <0.0-1.0: is every factual claim grounded in the context,
with nothing invented?>,
"notes": "<one short sentence>"}}"""


def load_golden() -> List[Dict]:
    if not GOLDEN_SET.exists():
        sys.exit(f"golden set not found: {GOLDEN_SET}")
    rows = []
    for line in GOLDEN_SET.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    live = [r for r in rows if "REPLACE" not in json.dumps(r)]
    if not live:
        sys.exit(
            "golden_set.jsonl still only contains REPLACE-ME placeholders — "
            "add 30-50 real QA questions first."
        )
    return live


def chunk_matches(chunk: Dict, expected: str) -> bool:
    p = chunk["payload"]
    haystacks = [
        source_label(p), p.get("file_path", ""), p.get("source_path", ""),
        p.get("jira_id", ""), p.get("tc_id", ""),
    ]
    e = expected.lower()
    return any(e in h.lower() for h in haystacks if h)


def judge(question: str, chunks: List[Dict], answer_text: str) -> Dict:
    from groq import Groq

    from backend.generate import format_context

    prompt = JUDGE_PROMPT.format(
        question=question,
        context=format_context(chunks)[:12000],
        answer=answer_text,
    )
    resp = Groq(api_key=config.GROQ_API_KEY).chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=300,
    )
    text = resp.choices[0].message.content or "{}"
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0) if m else text)
    except json.JSONDecodeError:
        return {"citation_correctness": 0.0, "faithfulness": 0.0,
                "notes": "judge returned unparseable output"}


def main() -> None:
    parser = argparse.ArgumentParser(description="QABuddyAI evaluation")
    parser.add_argument("--k", type=int, default=config.TOP_K_RERANK)
    parser.add_argument("--judge", action="store_true",
                        help="also generate answers and run the LLM judge")
    args = parser.parse_args()

    rows = load_golden()
    hits = 0
    cc_scores: List[float] = []
    faith_scores: List[float] = []

    for i, row in enumerate(rows, 1):
        question = row["question"]
        expected = row.get("expected_sources", [])
        chunks = retrieve(question, top_k=args.k)
        hit = any(
            chunk_matches(c, e) for e in expected for c in chunks
        ) if expected else False
        hits += hit
        line = f"[{i:>2}] hit@{args.k}: {'YES' if hit else 'no '} | {question[:70]}"

        if args.judge and chunks:
            from backend.generate import answer as generate_answer

            result = generate_answer(question, chunks)
            scores = judge(question, chunks, result["answer"])
            cc = float(scores.get("citation_correctness", 0.0))
            fa = float(scores.get("faithfulness", 0.0))
            cc_scores.append(cc)
            faith_scores.append(fa)
            line += f" | cite: {cc:.2f} faith: {fa:.2f} ({scores.get('notes', '')})"
        print(line)

    n = len(rows)
    print("\n=== summary ===")
    print(f"questions:        {n}")
    print(f"hit-rate@{args.k}:       {hits / n:.0%}")
    if cc_scores:
        print(f"citation correct: {sum(cc_scores) / len(cc_scores):.2f}")
        print(f"faithfulness:     {sum(faith_scores) / len(faith_scores):.2f}")


if __name__ == "__main__":
    main()
