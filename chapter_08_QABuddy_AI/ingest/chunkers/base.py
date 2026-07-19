"""Shared chunking primitives.

All chunkers return List[Chunk]. Token counts are approximated as chars/4 —
good enough for sizing budgets, and keeps ingestion dependency-free.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_text(path: Path) -> str:
    """Read text tolerantly (BOM-stripped, bad bytes replaced)."""
    return path.read_text(encoding="utf-8-sig", errors="replace")


_SEPARATORS = ["\n\n", "\n", ". ", " "]


def recursive_split(text: str, max_tokens: int, overlap_tokens: int = 0) -> List[str]:
    """Recursive character split on natural boundaries with token budgets."""
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    text = text.strip()
    if not text:
        return []
    if approx_tokens(text) <= max_tokens:
        return [text]

    for sep in _SEPARATORS:
        if sep in text:
            parts = [p for p in text.split(sep) if p.strip()]
            if len(parts) > 1:
                return _pack(parts, sep, max_chars, overlap_chars)
    # No separator worked: hard split.
    step = max(1, max_chars - overlap_chars)
    return [text[i : i + max_chars] for i in range(0, len(text), step)]


def _pack(parts: List[str], sep: str, max_chars: int, overlap_chars: int) -> List[str]:
    chunks: List[str] = []
    current = ""
    for part in parts:
        if len(part) > max_chars:  # oversized part: recurse deeper
            if current.strip():
                chunks.append(current.strip())
                current = ""
            chunks.extend(
                recursive_split(part, max_chars // 4, overlap_chars // 4)
            )
            continue
        candidate = (current + sep + part) if current else part
        if len(candidate) > max_chars:
            if current.strip():
                chunks.append(current.strip())
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = (tail + sep + part).strip() if tail else part
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def pack_units(units: List[str], max_tokens: int, overlap_units: int = 0) -> List[str]:
    """Pack pre-split units (methods, speaker turns, sections) into chunks.

    Units are never split themselves unless a single unit exceeds the budget,
    in which case it is recursively split (the "forced split" case).
    """
    chunks: List[str] = []
    current: List[str] = []
    size = 0
    for unit in units:
        t = approx_tokens(unit)
        if t > max_tokens:
            if current:
                chunks.append("\n\n".join(current))
                current, size = [], 0
            chunks.extend(recursive_split(unit, max_tokens))
            continue
        if size + t > max_tokens and current:
            chunks.append("\n\n".join(current))
            current = current[-overlap_units:] if overlap_units else []
            size = sum(approx_tokens(u) for u in current)
        current.append(unit)
        size += t
    if current:
        chunks.append("\n\n".join(current))
    return chunks


REQUIREMENT_ID_RE = re.compile(r"\b(?:REQ|FR|NFR|BR|US)[-_]?\d+(?:\.\d+)*\b", re.I)


def extract_requirement_ids(text: str) -> List[str]:
    return sorted({m.upper().replace("_", "-") for m in REQUIREMENT_ID_RE.findall(text)})
