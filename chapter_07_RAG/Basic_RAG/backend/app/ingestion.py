"""Document loading: reads PDF and plain-text files from the data directory
and splits them into chunks ready for embedding.

PDF text extraction is layered, cheapest-first:
  1. pypdf       - fast, handles the vast majority of normal PDFs
  2. pdfplumber  - a more forgiving parser; recovers text pypdf sometimes misses
  3. OCR         - last resort for PDFs with no real text layer at all (e.g.
                   design-tool exports that render text as vector outlines or
                   flattened images). Requires Tesseract + Poppler to be
                   installed on the machine (see README).
"""

import re
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from app.chunking import chunk_text, estimate_tokens
from app import config

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


def _clean_ocr_artifacts(text: str) -> str:
    """Tesseract commonly misreads a bullet glyph (•) as a bare lowercase
    "e" when a document's list markers use a font/encoding it can't map
    (this happens on the vector-outlined VWO PRD, for example). Restoring
    the bullet turns OCR'd lists back into readable lists instead of a
    line full of stray "e" characters."""
    return re.sub(r"(?m)^e(?=\s+\S)", "•", text)


def _extract_with_ocr(path: Path) -> str:
    """Rasterizes each page to an image and OCRs it. Only reached when both
    text-layer extractors come back empty."""
    from pdf2image import convert_from_path
    import pytesseract

    if config.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD

    convert_kwargs = {"dpi": config.OCR_DPI}
    if config.POPPLER_PATH:
        convert_kwargs["poppler_path"] = config.POPPLER_PATH

    images = convert_from_path(str(path), **convert_kwargs)
    pages = [pytesseract.image_to_string(image) for image in images]
    return _clean_ocr_artifacts("\n\n".join(pages))


def extract_pdf_text(path: Path) -> tuple[str, str]:
    """Returns (text, method_used) trying each extractor until one yields
    usable text."""
    text = _extract_with_pypdf(path)
    if len(text.strip()) >= MIN_USABLE_CHARS:
        return text, "pypdf"

    text = _extract_with_pdfplumber(path)
    if len(text.strip()) >= MIN_USABLE_CHARS:
        return text, "pdfplumber"

    text = _extract_with_ocr(path)
    return text, "ocr"


def extract_text_file(path: Path) -> str:
    # utf-8-sig strips a leading BOM if present (common in Windows-saved
    # .txt/.md files) and behaves identically to utf-8 otherwise.
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def load_documents(data_dir: Path) -> list[dict]:
    """Returns [{source, text, extraction_method}] for every supported file
    in data_dir."""
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
            docs.append({"source": path.name, "text": text, "extraction_method": method})
        elif suffix in SUPPORTED_TEXT_EXT:
            text = extract_text_file(path)
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
