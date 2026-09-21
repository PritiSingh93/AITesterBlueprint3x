"""Atlassian Document Format (ADF) to plain text.

Jira Cloud REST v3 returns rich text as a nested JSON tree. Reaching into
``description["content"][0]["content"][0]["text"]`` silently loses most of a
ticket, so the whole tree is walked instead.
"""

from __future__ import annotations

from typing import Any

_BLOCK_TYPES = {
    "paragraph",
    "heading",
    "listItem",
    "codeBlock",
    "blockquote",
    "panel",
    "tableRow",
    "rule",
}

_BULLET_PARENTS = {"bulletList", "orderedList"}


def adf_to_text(node: Any, _depth: int = 0) -> str:
    """Convert an ADF node (or a plain string) into readable text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(child, _depth) for child in node)
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")

    if node_type == "text":
        return str(node.get("text", ""))
    if node_type == "hardBreak":
        return "\n"
    if node_type == "rule":
        return "\n---\n"
    if node_type == "mention":
        attrs = node.get("attrs") or {}
        return str(attrs.get("text") or attrs.get("displayName") or "@mention")
    if node_type == "emoji":
        attrs = node.get("attrs") or {}
        return str(attrs.get("shortName", ""))
    if node_type == "inlineCard":
        attrs = node.get("attrs") or {}
        return str(attrs.get("url", ""))
    if node_type == "media":
        attrs = node.get("attrs") or {}
        return f"[media:{attrs.get('id', 'attachment')}]"

    inner = adf_to_text(node.get("content"), _depth + 1)

    if node_type in _BULLET_PARENTS:
        lines = [line for line in inner.split("\n") if line.strip()]
        return "\n".join(f"- {line.strip()}" for line in lines) + "\n"
    if node_type == "taskItem":
        attrs = node.get("attrs") or {}
        mark = "x" if attrs.get("state") == "DONE" else " "
        return f"- [{mark}] {inner.strip()}\n"
    if node_type == "tableCell" or node_type == "tableHeader":
        return f"{inner.strip()} | "
    if node_type in _BLOCK_TYPES:
        return inner + "\n"
    return inner


def normalize_text(value: str) -> str:
    """Collapse runaway blank lines produced by nested ADF blocks."""
    lines = [line.rstrip() for line in (value or "").split("\n")]
    out: list[str] = []
    blanks = 0
    for line in lines:
        if line.strip():
            blanks = 0
            out.append(line)
        else:
            blanks += 1
            if blanks <= 1:
                out.append("")
    return "\n".join(out).strip()


def extract_text(field_value: Any) -> str:
    """Public entry point: ADF tree, plain string or ``None`` to clean text."""
    return normalize_text(adf_to_text(field_value))
