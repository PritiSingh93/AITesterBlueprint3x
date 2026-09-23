"""Local retrieval over the team's existing test-case library.

Used by 013 to answer one question before planning: *has someone already
written this test?* Without it the planner happily produces a sixth variant of
"verify login with valid credentials" that the library has covered for years.

No embedding API and no vector database. The corpus is a few thousand short
documents, which pure-Python TF-IDF handles in milliseconds, and keeping it
dependency-free means the chapter runs offline and on any Python version.

TF-IDF matches on shared words, not meaning: it will not connect "cart" to
"basket". For a library that uses consistent product vocabulary that is
usually enough, and when it is not, the low scores say so honestly rather than
returning a confident wrong answer.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from pathlib import Path

# The 2000-case VWO export from chapter 7. A local tta_test_cases.json next to
# this file wins if present, so a lesson can use a smaller, tailored library.
_HERE = Path(__file__).resolve().parent
_LOCAL_JSON = _HERE / "tta_test_cases.json"
_VWO_CSV = (
    _HERE.parents[2] / "chapter_07_RAG" / "Advance_RAG" / "testcase" / "VWO_2000_Test_Cases.csv"
)

_WORD = re.compile(r"[a-z0-9]+")

# Words that appear in nearly every test case carry no signal and would let a
# query match anything.
_STOPWORDS = frozenset("""
a an and are as at be by for from has have in is it its of on or that the to
with verify check ensure confirm validate test case step steps user should
when then given expect expected result system page click enter open
""".split())


def _tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower())
            if len(w) > 1 and w not in _STOPWORDS]


def _split_tags(raw) -> list[str]:
    if isinstance(raw, list):
        return [t for t in raw if t]
    return [t.strip() for t in re.split(r"[;,]", str(raw or "")) if t.strip()]


def _type_from(tags: list[str], fallback: str = "functional") -> str:
    """The export has no explicit type column, so read it off the tags."""
    known = ("regression", "smoke", "security", "performance", "accessibility",
             "integration", "analytics", "sanity")
    for tag in tags:
        if tag.lower() in known:
            return tag.lower()
    return fallback


class TestCaseRAG:
    """An in-memory TF-IDF index over the existing test-case library."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path, self.cases = self._load(path)
        self.backend = f"tf-idf (pure python) over {self.path.name}"
        self._build_index()

    # -- loading ----------------------------------------------------------

    def _load(self, path: str | Path | None) -> tuple[Path, list[dict]]:
        for candidate in ([Path(path)] if path else []) + [_LOCAL_JSON, _VWO_CSV]:
            if candidate.exists():
                rows = (self._read_json(candidate) if candidate.suffix == ".json"
                        else self._read_csv(candidate))
                if rows:
                    return candidate, rows
        raise FileNotFoundError(
            f"No test-case library found. Looked for {_LOCAL_JSON} and {_VWO_CSV}."
        )

    @staticmethod
    def _read_json(path: Path) -> list[dict]:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["cases"] if isinstance(data, dict) else data
        return [TestCaseRAG._normalise(r) for r in rows]

    @staticmethod
    def _read_csv(path: Path) -> list[dict]:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return [TestCaseRAG._normalise(r) for r in csv.DictReader(fh)]

    @staticmethod
    def _normalise(row: dict) -> dict:
        """One shape for the rest of the program, whatever the source file.

        ``status`` and ``last_result`` are placeholders, not inventions: the
        export carries no run history, and a fabricated "passed" would mislead
        the planner into trusting coverage that was never demonstrated.
        """
        tags = _split_tags(row.get("tags"))
        return {
            "id": (row.get("id") or row.get("jira_id") or "").strip(),
            "jira_id": (row.get("jira_id") or "").strip(),
            "title": (row.get("title") or "").strip(),
            "module": (row.get("module") or "").strip(),
            "priority": (row.get("priority") or "").strip(),
            "type": row.get("type") or _type_from(tags),
            "status": row.get("status") or "in library",
            "last_result": row.get("last_result") or "unrecorded",
            "steps": (row.get("steps") or "").strip(),
            "expected": (row.get("expected") or "").strip(),
            "preconditions": (row.get("preconditions") or "").strip(),
            "tags": tags,
        }

    # -- indexing ---------------------------------------------------------

    def _text_of(self, case: dict) -> str:
        return " ".join([
            case["title"], case["module"], case["steps"],
            case["expected"], " ".join(case["tags"]),
        ])

    def _build_index(self) -> None:
        docs = [_tokenize(self._text_of(c)) for c in self.cases]
        n = len(docs) or 1

        df: Counter[str] = Counter()
        for tokens in docs:
            df.update(set(tokens))
        # Smoothed idf, so a term in every document still scores above zero.
        self._idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

        self._vectors: list[dict[str, float]] = []
        for tokens in docs:
            self._vectors.append(self._vectorize(tokens))

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        """Term frequency times idf, L2-normalised so cosine is a dot product."""
        if not tokens:
            return {}
        counts = Counter(tokens)
        vec = {t: (c / len(tokens)) * self._idf.get(t, 0.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {t: v / norm for t, v in vec.items()} if norm else {}

    # -- querying ---------------------------------------------------------

    def search(self, query: str, k: int = 5) -> list[tuple[float, dict]]:
        """Return the k most similar cases as (score, case), best first."""
        q = self._vectorize(_tokenize(query))
        if not q:
            return []

        scored = []
        for vec, case in zip(self._vectors, self.cases, strict=True):
            # Iterate the shorter side; a query has far fewer terms than a doc.
            score = sum(w * vec.get(t, 0.0) for t, w in q.items())
            if score > 0:
                scored.append((score, case))

        scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
        return scored[:k]


def format_for_prompt(hits: list[tuple[float, dict]]) -> str:
    """Render retrieved cases for a planner prompt.

    The similarity score is included deliberately. A planner told that the best
    match scored 0.08 can conclude the library covers nothing here, which is a
    different and more useful answer than treating the top hit as relevant
    because it happened to come first.
    """
    if not hits:
        return "No similar test cases were found in the library."

    blocks = []
    for score, c in hits:
        lines = [
            f"[{c['id']}] {c['title']}",
            f"  similarity : {score:.3f}",
            f"  module     : {c['module'] or 'n/a'}   type: {c['type']}   "
            f"priority: {c['priority'] or 'n/a'}",
            f"  status     : {c['status']}   last result: {c['last_result']}",
        ]
        if c["tags"]:
            lines.append(f"  tags       : {', '.join(c['tags'][:8])}")
        if c["steps"]:
            lines.append(f"  steps      : {c['steps'][:300]}")
        if c["expected"]:
            lines.append(f"  expected   : {c['expected'][:200]}")
        blocks.append("\n".join(lines))

    return (
        f"{len(hits)} most similar case(s) already in the library, best first.\n"
        "Similarity is word overlap on a 0-1 scale; below roughly 0.15 means the\n"
        "library probably does not cover this at all.\n\n" + "\n\n".join(blocks)
    )
