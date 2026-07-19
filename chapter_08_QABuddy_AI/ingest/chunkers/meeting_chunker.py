"""Meeting notes / transcript chunker: split by topic/speaker turn,
300-500 tokens, 10% overlap (last turn repeated).

Handles .txt/.md notes and .vtt/.srt subtitle exports (timestamps stripped).
Filename convention YYYY-MM-DD_topic.md feeds meeting_date metadata.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from ingest.chunkers.base import Chunk, pack_units, read_text

MAX_TOKENS = 500
OVERLAP_UNITS = 1  # ~10%: repeat the previous speaker turn

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_SPEAKER_RE = re.compile(r"^[A-Z][\w .'\-]{0,40}:\s")
_VTT_NOISE = re.compile(
    r"^(WEBVTT.*|\d+|\s*|[\d:.,]+\s*-->\s*[\d:.,]+.*)$"
)


def _to_plain(path: Path, text: str) -> str:
    if path.suffix.lower() not in (".vtt", ".srt"):
        return text
    lines = [l for l in text.splitlines() if not _VTT_NOISE.match(l)]
    return "\n".join(lines)


def _turns(text: str) -> List[str]:
    """Split into speaker turns; fall back to blank-line topic blocks."""
    turns: List[str] = []
    current: List[str] = []
    has_speakers = any(_SPEAKER_RE.match(l) for l in text.splitlines())
    for line in text.splitlines():
        boundary = _SPEAKER_RE.match(line) if has_speakers else (not line.strip())
        if boundary and current and "".join(current).strip():
            turns.append("\n".join(current).strip())
            current = []
        if line.strip() or not has_speakers:
            current.append(line)
    if current and "".join(current).strip():
        turns.append("\n".join(current).strip())
    return [t for t in turns if t]


def chunk_meeting(path: Path, rel_path: str) -> List[Chunk]:
    text = _to_plain(path, read_text(path))
    if not text.strip():
        return []
    m = _DATE_RE.search(path.name)
    meeting_date = m.group(1) if m else ""
    title = re.sub(r"^\d{4}-\d{2}-\d{2}[_\- ]*", "", path.stem).replace("_", " ")

    chunks = []
    for piece in pack_units(_turns(text), MAX_TOKENS, overlap_units=OVERLAP_UNITS):
        header = f"Meeting: {title}" + (f" ({meeting_date})" if meeting_date else "")
        chunks.append(
            Chunk(
                text=f"{header}\n{piece}",
                metadata={
                    "title": title,
                    "meeting_date": meeting_date,
                    "file_path": rel_path,
                    "source_type": "meeting",
                },
            )
        )
    return chunks
