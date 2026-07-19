"""Test-case chunker: one CSV/XLSX row = one chunk (150-300 tokens, no overlap).

Column names are matched case/format-insensitively against common aliases, so
testdata.csv doesn't have to follow one exact header set. Unmapped columns are
appended to the chunk text so no information is silently dropped.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import pandas as pd

from ingest.chunkers.base import Chunk

COLUMN_ALIASES: Dict[str, List[str]] = {
    "tc_id": ["tc_id", "tcid", "id", "case_id", "test_case_id", "tc_no", "tc_number"],
    "title": ["title", "name", "summary", "test_case", "testcase", "scenario",
              "test_case_name", "testcase_name"],
    "steps": ["steps", "test_steps", "procedure", "actions", "description"],
    "expected": ["expected", "expected_result", "expected_results", "result"],
    "module": ["module", "component", "feature", "area", "suite"],
    "priority": ["priority", "severity"],
    "automation_status": ["automation_status", "automation", "automated", "execution_type"],
    "linked_jira_id": ["linked_jira_id", "linked_jira", "jira", "jira_id",
                       "jira_key", "defect_id", "bug_id"],
}


def _norm(col: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", col.strip().lower()).strip("_")


def _map_columns(df: pd.DataFrame) -> Dict[str, str]:
    normalized = {_norm(c): c for c in df.columns}
    mapping: Dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized and normalized[alias] not in mapping.values():
                mapping[field] = normalized[alias]
                break
    return mapping


def chunk_testcases(path: Path, rel_path: str) -> List[Chunk]:
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
    else:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [str(c) for c in df.columns]
    mapping = _map_columns(df)
    mapped_cols = set(mapping.values())

    chunks: List[Chunk] = []
    for idx, row in df.iterrows():
        get = lambda f: str(row[mapping[f]]).strip() if f in mapping else ""  # noqa: E731
        tc_id = get("tc_id") or f"{path.stem}-row{int(idx) + 2}"  # +2: header + 1-based

        lines = [f"Test Case {tc_id}: {get('title')}"]
        if get("module"):
            lines.append(f"Module: {get('module')}")
        if get("priority"):
            lines.append(f"Priority: {get('priority')}")
        if get("steps"):
            lines.append(f"Steps:\n{get('steps')}")
        if get("expected"):
            lines.append(f"Expected Result:\n{get('expected')}")
        # Keep unmapped columns too — no silent data loss.
        for col in df.columns:
            if col not in mapped_cols and str(row[col]).strip():
                lines.append(f"{col}: {str(row[col]).strip()}")

        text = "\n".join(lines).strip()
        if not text:
            continue
        chunks.append(
            Chunk(
                text=text,
                metadata={
                    "tc_id": tc_id,
                    "title": get("title"),
                    "module": get("module"),
                    "priority": get("priority"),
                    "automation_status": get("automation_status"),
                    "linked_jira_id": get("linked_jira_id"),
                    "jira_id": get("linked_jira_id"),  # shared indexed key
                    "file_path": rel_path,
                    "row": int(idx) + 2,
                    "source_type": "test_case",
                },
            )
        )
    return chunks
