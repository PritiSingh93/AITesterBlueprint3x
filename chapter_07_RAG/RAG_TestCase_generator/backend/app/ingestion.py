"""Document loading: reads PDF and plain-text files from the data directory
and splits them into chunks ready for embedding.

PDF text extraction tries pypdf first, then falls back to pdfplumber for
PDFs pypdf can't parse cleanly. A file that still yields no usable text
(or throws) is skipped rather than aborting the whole ingestion batch.
"""

from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from app.chunking import chunk_text, estimate_tokens

SUPPORTED_TEXT_EXT = {".txt", ".md"}

# A doc is treated as "no usable text" below this many non-whitespace chars,
# which triggers the next extraction method in the fallback chain.
MIN_USABLE_CHARS = 20


def _extract_with_pypdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def _extract_with_pdfplumber(path: Path) -> str:
    with pdfplumber.open(str(path)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages)


def extract_pdf_text(path: Path) -> tuple[str, str]:
    """Returns (text, method_used) trying each extractor until one yields
    usable text."""
    text = _extract_with_pypdf(path)
    if len(text.strip()) >= MIN_USABLE_CHARS:
        return text, "pypdf"

    text = _extract_with_pdfplumber(path)
    return text, "pdfplumber"


def extract_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_documents(data_dir: Path) -> list[dict]:
    """Returns [{source, text, extraction_method}] for every supported file
    in data_dir. Files that fail to extract are skipped, not fatal."""
    docs: list[dict] = []
    if not data_dir.exists():
        return docs

    for path in sorted(data_dir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                text, method = extract_pdf_text(path)
            except Exception:
                continue
            if len(text.strip()) < MIN_USABLE_CHARS:
                continue
            docs.append({"source": path.name, "text": text, "extraction_method": method})
        elif suffix in SUPPORTED_TEXT_EXT:
            text = extract_text_file(path)
            if not text.strip():
                continue
            docs.append({"source": path.name, "text": text, "extraction_method": "text"})
    return docs


def build_chunks(data_dir: Path) -> list[dict]:
    """Loads every document and returns a flat list of chunk records:
    {id, source, chunk_index, text, char_count, est_tokens, extraction_method}
    """
    all_chunks: list[dict] = []
    for doc in load_documents(data_dir):
        pieces = chunk_text(doc["text"])
        for idx, piece in enumerate(pieces):
            all_chunks.append(
                {
                    "id": f"{doc['source']}::chunk-{idx}",
                    "source": doc["source"],
                    "chunk_index": idx,
                    "text": piece,
                    "char_count": len(piece),
                    "est_tokens": estimate_tokens(piece),
                    "extraction_method": doc["extraction_method"],
                }
            )
    return all_chunks
