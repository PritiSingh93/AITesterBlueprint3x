"""Document chunker for company docs (05) and PRD/SRS/BRD/FRD (09).

Header-first recursive split, 500-800 tokens, 15% overlap. Requirement IDs
(REQ-1, FR-2.3, ...) are preserved in the text AND extracted into
metadata.requirement_ids — this powers RTM building and coverage-gap answers.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from ingest.chunkers.base import Chunk, extract_requirement_ids, read_text, recursive_split

MAX_TOKENS = 800
OVERLAP_TOKENS = 120  # ~15%

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_DOC_KIND = re.compile(r"^(prd|srs|brd|frd)[\s_-]", re.I)


def load_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader  # lazy: optional-ish dependency

        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == ".docx":
        import docx  # python-docx

        d = docx.Document(str(path))
        return "\n\n".join(p.text for p in d.paragraphs if p.text.strip())
    return read_text(path)


def _md_sections(text: str) -> List[Tuple[str, str]]:
    """Split Markdown into (heading, body) sections; heading may be ''."""
    sections: List[Tuple[str, str]] = []
    heading = ""
    body: List[str] = []
    for line in text.splitlines():
        m = _MD_HEADING.match(line)
        if m:
            if body and "".join(body).strip():
                sections.append((heading, "\n".join(body)))
            heading, body = m.group(2).strip(), []
        else:
            body.append(line)
    if body and "".join(body).strip():
        sections.append((heading, "\n".join(body)))
    return sections or [("", text)]


def chunk_doc(path: Path, rel_path: str, source_type: str = "doc") -> List[Chunk]:
    text = load_document_text(path)
    if not text.strip():
        return []

    doc_kind = ""
    if source_type == "prd":
        m = _DOC_KIND.match(path.name)
        doc_kind = m.group(1).lower() if m else "prd"

    sections = (
        _md_sections(text) if path.suffix.lower() in (".md", ".markdown") else [("", text)]
    )

    chunks: List[Chunk] = []
    for heading, body in sections:
        for piece in recursive_split(body, MAX_TOKENS, OVERLAP_TOKENS):
            out = f"# {heading}\n{piece}" if heading else piece
            chunks.append(
                Chunk(
                    text=out,
                    metadata={
                        "title": path.stem,
                        "file_path": rel_path,
                        "section_heading": heading,
                        "requirement_ids": extract_requirement_ids(out),
                        "doc_kind": doc_kind,
                        "source_type": source_type,
                    },
                )
            )
    return chunks
