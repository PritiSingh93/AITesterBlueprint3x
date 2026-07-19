"""JIRA chunker: one ticket = one chunk; split by comment thread past ~800
tokens with the ticket ID repeated in every sub-chunk.

Accepts either raw JIRA REST issue JSON ({"key": ..., "fields": {...}}), the
simplified flat shape written by jira_sync.py, or files containing a list /
{"issues": [...]} of either.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ingest.chunkers.base import Chunk, approx_tokens, pack_units, recursive_split

MAX_TOKENS = 800


def _adf_to_text(node: Any) -> str:
    """Flatten Atlassian Document Format (or any nested JSON) to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(t for t in (_adf_to_text(n) for n in node) if t)
    if isinstance(node, dict):
        if node.get("type") == "text":
            return str(node.get("text", ""))
        return _adf_to_text(node.get("content"))
    return ""


def _get(fields: Dict, *names, default: str = "") -> Any:
    for n in names:
        if n in fields and fields[n] is not None:
            return fields[n]
    return default


def _name_of(v: Any) -> str:
    if isinstance(v, dict):
        return str(v.get("name") or v.get("displayName") or v.get("value") or "")
    return str(v or "")


def _issue_to_record(data: Dict) -> Dict:
    fields = data.get("fields", data)
    comments_raw = _get(fields, "comment", "comments", default=[])
    if isinstance(comments_raw, dict):
        comments_raw = comments_raw.get("comments", [])
    comments = []
    for c in comments_raw or []:
        if isinstance(c, str):
            comments.append({"author": "", "body": c})
        else:
            comments.append(
                {
                    "author": _name_of(c.get("author")),
                    "created": str(c.get("created", ""))[:10],
                    "body": _adf_to_text(c.get("body")),
                }
            )
    key = str(data.get("key") or fields.get("key") or "UNKNOWN-0")
    return {
        "key": key,
        "project": key.split("-")[0],
        "summary": _name_of(_get(fields, "summary")),
        "description": _adf_to_text(_get(fields, "description")),
        "status": _name_of(_get(fields, "status")),
        "priority": _name_of(_get(fields, "priority")),
        "issue_type": _name_of(_get(fields, "issuetype", "issue_type")),
        "sprint": _name_of(_get(fields, "sprint")),
        "labels": _get(fields, "labels", default=[]) or [],
        "assignee": _name_of(_get(fields, "assignee")),
        "updated_date": str(_get(fields, "updated", "updated_date"))[:19],
        "comments": comments,
    }


def _issues_in_file(data: Any) -> List[Dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("issues"), list):
        return data["issues"]
    return [data]


def chunk_jira_file(path: Path, rel_path: str) -> List[Chunk]:
    data = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    chunks: List[Chunk] = []
    for raw in _issues_in_file(data):
        rec = _issue_to_record(raw)
        key = rec["key"]
        meta = {
            "jira_id": key,
            "jira_key": key,
            "project": rec["project"],
            "status": rec["status"],
            "priority": rec["priority"],
            "issue_type": rec["issue_type"],
            "sprint": rec["sprint"],
            "labels": rec["labels"],
            "assignee": rec["assignee"],
            "updated_date": rec["updated_date"],
            "file_path": rel_path,
            "source_type": "jira",
        }

        head_lines = [
            f"[{key}] {rec['summary']}",
            f"Type: {rec['issue_type']} | Status: {rec['status']} | "
            f"Priority: {rec['priority']} | Assignee: {rec['assignee']}",
        ]
        if rec["labels"]:
            head_lines.append("Labels: " + ", ".join(map(str, rec["labels"])))
        if rec["description"]:
            head_lines.append(f"Description:\n{rec['description']}")
        head = "\n".join(head_lines)

        comment_units = [
            f"Comment by {c.get('author', '')} {c.get('created', '')}:\n{c['body']}".strip()
            for c in rec["comments"]
            if c.get("body")
        ]
        full = head + ("\n\n" + "\n\n".join(comment_units) if comment_units else "")

        if approx_tokens(full) <= MAX_TOKENS:
            chunks.append(Chunk(text=full, metadata=dict(meta)))
            continue

        # Oversized ticket: head chunk(s) + comment-thread chunks, ticket ID
        # repeated in every sub-chunk.
        for part in recursive_split(head, MAX_TOKENS):
            text = part if part.startswith(f"[{key}]") else f"[{key}] {part}"
            chunks.append(Chunk(text=text, metadata=dict(meta)))
        for i, packed in enumerate(pack_units(comment_units, MAX_TOKENS), 1):
            chunks.append(
                Chunk(text=f"[{key}] Comments (part {i}):\n{packed}", metadata=dict(meta))
            )
    return chunks
