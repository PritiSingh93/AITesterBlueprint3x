"""JIRA sync through the JIRA MCP connection (never the REST API directly).

Runs the JQL from config/jql.txt via the MCP server's search tool, saves one
raw JSON snapshot per issue into 04_JIRA_Tickets/, then chunks + upserts only
the fetched issues. A state file tracks the last successful sync so --delta
runs only pick up issues updated since then (phase-2 hourly mode).

Usage:
    python ingest/jira_sync.py               # full JQL
    python ingest/jira_sync.py --delta       # JQL AND updated >= last sync
    python ingest/jira_sync.py --dry-run     # fetch + save JSON, no upsert

Required env (owner provides the connection):
    JIRA_MCP_URL          e.g. https://mcp.atlassian.com/v1/sse or a local MCP
    JIRA_MCP_TOKEN        bearer token if the server needs one
    JIRA_MCP_SEARCH_TOOL  tool name (default: searchJiraIssuesUsingJql)
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import config  # noqa: E402

STATE_FILE = config.STATE_DIR / "jira_sync.json"
JIRA_DIR_KEY = "jira"


def read_jql() -> str:
    if not config.JQL_FILE.exists():
        sys.exit(f"JQL file not found: {config.JQL_FILE}")
    lines = [
        l.strip()
        for l in config.JQL_FILE.read_text(encoding="utf-8-sig").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if not lines:
        sys.exit(f"No JQL found in {config.JQL_FILE} (only comments?)")
    return " ".join(lines)


def load_state() -> Dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: Dict) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------- #
# MCP fetch                                                                    #
# --------------------------------------------------------------------------- #
def _parse_issues(payload: Any) -> List[Dict]:
    if isinstance(payload, list):
        return [p for p in payload if isinstance(p, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("issues"), list):
            return payload["issues"]
        if payload.get("key"):
            return [payload]
    return []


async def fetch_issues(jql: str, max_results: int = 100) -> List[Dict]:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError:
        sys.exit("The 'mcp' package is required: pip install mcp")

    headers = (
        {"Authorization": f"Bearer {config.JIRA_MCP_TOKEN}"}
        if config.JIRA_MCP_TOKEN
        else None
    )
    async with streamablehttp_client(config.JIRA_MCP_URL, headers=headers) as (
        read, write, _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                config.JIRA_MCP_SEARCH_TOOL,
                {"jql": jql, "maxResults": max_results},
            )
            issues: List[Dict] = []
            for content in result.content:
                if getattr(content, "type", "") != "text":
                    continue
                try:
                    issues.extend(_parse_issues(json.loads(content.text)))
                except json.JSONDecodeError:
                    continue
            if not issues and result.isError:
                sys.exit(f"MCP tool error: {result.content}")
            return issues


# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="QABuddyAI JIRA sync (via MCP)")
    parser.add_argument("--delta", action="store_true",
                        help="only issues updated since the last successful sync")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and save JSON snapshots, skip embedding")
    parser.add_argument("--max-results", type=int, default=100)
    args = parser.parse_args()

    if not config.JIRA_MCP_URL:
        sys.exit(
            "JIRA_MCP_URL is not set. Add the MCP connection details to .env "
            "(JIRA_MCP_URL, JIRA_MCP_TOKEN, JIRA_MCP_SEARCH_TOOL)."
        )

    jql = read_jql()
    state = load_state()
    if args.delta and state.get("last_sync"):
        jql = f'({jql}) AND updated >= "{state["last_sync"]}"'
    started = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")

    print(f"JQL: {jql}")
    issues = asyncio.run(fetch_issues(jql, args.max_results))
    print(f"fetched {len(issues)} issue(s)")

    folder_name, _ = config.SOURCES[JIRA_DIR_KEY]
    out_dir = config.DATA_ROOT / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    saved: List[Path] = []
    for issue in issues:
        key = str(issue.get("key", "")).strip()
        if not key:
            continue
        path = out_dir / f"{key}.json"
        path.write_text(
            json.dumps(issue, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        saved.append(path)
    print(f"saved {len(saved)} snapshot(s) to {out_dir}")

    if not args.dry_run and saved:
        # Ingest just the fetched files, sharing the manifest with
        # run_full_ingest so batch runs don't redo this work.
        from ingest.chunkers.base import sha256_file
        from ingest.chunkers.jira_chunker import chunk_jira_file
        from ingest.embed_and_upsert import (
            delete_source_path, ensure_collection, upsert_chunks,
        )
        from ingest.run_full_ingest import load_manifest, save_manifest

        ensure_collection()
        manifest = load_manifest()
        points = 0
        for path in saved:
            rel = path.relative_to(config.DATA_ROOT).as_posix()
            digest = sha256_file(path)
            if manifest.get(rel) == digest:
                continue
            if rel in manifest:
                delete_source_path(rel)
            points += upsert_chunks(
                chunk_jira_file(path, path.name), rel, digest
            )
            manifest[rel] = digest
        save_manifest(manifest)
        print(f"upserted {points} chunk(s)")

    state["last_sync"] = started
    save_state(state)
    print(f"last_sync -> {started}")


if __name__ == "__main__":
    main()
