"""Text chunking for the RAG pipeline.

Splits raw document text into overlapping chunks sized to land in the
requested 500-1000 token range (using a ~4-chars-per-token estimate),
while trying to break on paragraph/sentence boundaries rather than
mid-word.
"""

import re

from app.config import CHUNK_OVERLAP_CHARS, CHUNK_TARGET_CHARS

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _split_into_paragraphs(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(paragraphs) > 1:
        return paragraphs
    # PDFs often extract as one blob with single newlines only - fall back
    # to sentence-level splitting so we still have natural break points.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    target_chars: int = CHUNK_TARGET_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    text = text.strip()
    if not text:
        return []

    paragraphs = _split_into_paragraphs(text)
    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        if len(para) > target_chars:
            # Hard-split an oversized paragraph/sentence on its own.
            flush()
            step = max(1, target_chars - overlap_chars)
            for i in range(0, len(para), step):
                piece = para[i : i + target_chars]
                if piece.strip():
                    chunks.append(piece.strip())
            continue

        if current and len(current) + len(para) + 2 > target_chars:
            flush()
            tail = current[-overlap_chars:] if len(current) > overlap_chars else current
            current = f"{tail}\n\n{para}" if tail else para
        else:
            current = f"{current}\n\n{para}" if current else para

    flush()
    return chunks
