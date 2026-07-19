"""AST-aware code chunker for the Selenium (Java) and Playwright (TS/JS) repos.

Rules (prompt.md): split by function/class, 300-500 tokens, no overlap except
forced splits on oversized functions.

Strategy: parse with tree-sitter and walk the tree top-down — any node that
fits the token budget becomes a unit; bigger nodes are descended into, so a
method is never cut unless the method itself exceeds the budget. Consecutive
units are then packed back together up to the budget. If tree-sitter is not
installed we fall back to a brace-depth-aware regex splitter.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from ingest.chunkers.base import Chunk, approx_tokens, pack_units, read_text, recursive_split

MAX_TOKENS = 500

LANGS = {
    ".java": "java",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".mjs": "javascript",
}

try:
    from tree_sitter_language_pack import get_parser  # type: ignore

    _HAVE_TS = True
except Exception:  # pragma: no cover - optional dependency
    _HAVE_TS = False


# --------------------------------------------------------------------------- #
# Unit extraction                                                              #
# --------------------------------------------------------------------------- #
def _units_tree_sitter(src: str, lang: str) -> List[str]:
    parser = get_parser(lang)
    tree = parser.parse(src.encode("utf-8"))
    raw = src.encode("utf-8")
    units: List[str] = []

    def collect(node) -> None:
        text = raw[node.start_byte : node.end_byte].decode("utf-8", "replace")
        if approx_tokens(text) <= MAX_TOKENS or not node.children:
            if text.strip():
                units.append(text)
            return
        for child in node.children:
            collect(child)

    collect(tree.root_node)
    return units


_JAVA_BOUNDARY = re.compile(
    r"^\s*(?:@\w+|(?:public|private|protected|static|final|abstract|synchronized)\b)"
)
_TSJS_BOUNDARY = re.compile(
    r"^\s*(?:(?:export\s+)?(?:async\s+)?function\b|(?:export\s+)?(?:const|let|var|class)\b"
    r"|(?:it|test|describe)(?:\.\w+)?\s*\()"
)


def _units_regex(src: str, lang: str) -> List[str]:
    """Fallback: start a new unit at declaration boundaries that sit at
    class/file level (brace depth <= 1), so we never cut inside a method."""
    boundary = _JAVA_BOUNDARY if lang == "java" else _TSJS_BOUNDARY
    units: List[str] = []
    current: List[str] = []
    depth = 0
    for line in src.splitlines():
        if boundary.match(line) and depth <= 1 and current:
            units.append("\n".join(current))
            current = []
        current.append(line)
        depth += line.count("{") - line.count("}")
    if current:
        units.append("\n".join(current))
    return [u for u in units if u.strip()]


# --------------------------------------------------------------------------- #
# Best-effort name extraction (for metadata / citations)                       #
# --------------------------------------------------------------------------- #
_CLASS_RE = re.compile(r"\b(?:class|interface|enum)\s+(\w+)")
_JAVA_METHOD_RE = re.compile(
    r"(?:public|private|protected)[\w\s<>\[\],]*?\s(\w+)\s*\("
)
_TSJS_NAME_RE = re.compile(
    r"(?:function\s+(\w+)|(?:it|test|describe)(?:\.\w+)?\s*\(\s*['\"`](.{1,80}?)['\"`])"
)


def _names(chunk_text: str, lang: str, file_class: str) -> tuple[str, str]:
    class_name = file_class
    m = _CLASS_RE.search(chunk_text)
    if m:
        class_name = m.group(1)
    method_name = ""
    if lang == "java":
        m = _JAVA_METHOD_RE.search(chunk_text)
        if m:
            method_name = m.group(1)
    else:
        m = _TSJS_NAME_RE.search(chunk_text)
        if m:
            method_name = m.group(1) or m.group(2) or ""
    return class_name, method_name


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
def chunk_code_file(
    path: Path,
    rel_path: str,
    repo_name: str,
    source_type: str,
    commit_hash: str = "",
) -> List[Chunk]:
    src = read_text(path)
    if not src.strip():
        return []
    lang = LANGS.get(path.suffix.lower())

    if lang is None:
        # Config-ish files in the repos (xml, properties, json, md): plain
        # split, no overlap.
        texts = recursive_split(src, MAX_TOKENS)
    else:
        if _HAVE_TS:
            try:
                units = _units_tree_sitter(src, lang)
            except Exception:
                units = _units_regex(src, lang)
        else:
            units = _units_regex(src, lang)
        texts = pack_units(units, MAX_TOKENS)

    file_class = ""
    m = _CLASS_RE.search(src)
    if m:
        file_class = m.group(1)

    comment = "//" if lang else "#"
    chunks: List[Chunk] = []
    for text in texts:
        class_name, method_name = _names(text, lang or "java", file_class)
        header = f"{comment} {repo_name}/{rel_path}"
        if class_name:
            header += f" :: {class_name}" + (f".{method_name}" if method_name else "")
        chunks.append(
            Chunk(
                text=f"{header}\n{text}",
                metadata={
                    "repo_name": repo_name,
                    "file_path": rel_path,
                    "class_name": class_name,
                    "method_name": method_name,
                    "last_commit_hash": commit_hash,
                    "source_type": source_type,
                },
            )
        )
    return chunks
