"""Lucidchart chunker: one diagram / sub-flow = one chunk, 300-600 tokens,
no overlap. Input is text exports (Markdown with headings/Mermaid blocks or
`---` dividers between flows).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from ingest.chunkers.base import Chunk, read_text, recursive_split

MAX_TOKENS = 600

_DIVIDER = re.compile(r"^(#{1,3}\s+.*|---+\s*)$")


def _flows(text: str) -> List[str]:
    flows: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if _DIVIDER.match(line) and current and "".join(current).strip():
            flows.append("\n".join(current).strip())
            current = []
        if not re.fullmatch(r"---+\s*", line):
            current.append(line)
    if current and "".join(current).strip():
        flows.append("\n".join(current).strip())
    return [f for f in flows if f]


def chunk_lucidchart(path: Path, rel_path: str) -> List[Chunk]:
    text = read_text(path)
    if not text.strip():
        return []
    diagram_name = path.stem.replace("_", " ")
    chunks = []
    # One flow = one chunk (never merge flows); split only oversized flows.
    for flow in _flows(text):
        for piece in recursive_split(flow, MAX_TOKENS):
            chunks.append(
                Chunk(
                    text=f"Diagram: {diagram_name}\n{piece}",
                    metadata={
                        "diagram_name": diagram_name,
                        "file_path": rel_path,
                        "source_type": "diagram",
                    },
                )
            )
    return chunks
