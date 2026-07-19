"""Phase-1 ingestion entrypoint: walk the 10 data-source folders, chunk each
file with its source-specific chunker, embed, and upsert into Qdrant.

Usage:
    python ingest/run_full_ingest.py --source all
    python ingest/run_full_ingest.py --source selenium,testcases
    python ingest/run_full_ingest.py --source all --full   # ignore manifest

Delta by default: a manifest (ingest/.state/manifest.json) maps every ingested
file to its content hash — unchanged files are skipped, changed files are
deleted+re-upserted, deleted files have their vectors removed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import config  # noqa: E402
from ingest.chunkers.base import Chunk, sha256_file  # noqa: E402
from ingest.chunkers.code_chunker import chunk_code_file  # noqa: E402
from ingest.chunkers.doc_chunker import chunk_doc  # noqa: E402
from ingest.chunkers.jenkins_chunker import chunk_jenkins  # noqa: E402
from ingest.chunkers.jira_chunker import chunk_jira_file  # noqa: E402
from ingest.chunkers.lucidchart_chunker import chunk_lucidchart  # noqa: E402
from ingest.chunkers.meeting_chunker import chunk_meeting  # noqa: E402
from ingest.chunkers.testcase_chunker import chunk_testcases  # noqa: E402
from ingest.embed_and_upsert import (  # noqa: E402
    delete_source_path,
    ensure_collection,
    upsert_chunks,
)

SKIP_DIRS = {
    ".git", "node_modules", "target", "build", "dist", "out", "__pycache__",
    ".idea", ".vscode", "test-results", "playwright-report", "allure-results",
    ".venv", "venv",
}
SKIP_FILES = {".gitkeep", "package-lock.json", "yarn.lock"}

EXTENSIONS: Dict[str, set] = {
    "selenium":   {".java", ".xml", ".properties", ".md"},
    "playwright": {".ts", ".tsx", ".js", ".mjs", ".md", ".json"},
    "testcases":  {".csv", ".xlsx", ".xls"},
    "jira":       {".json"},
    "docs":       {".pdf", ".md", ".txt", ".docx"},
    "meetings":   {".txt", ".md", ".vtt", ".srt"},
    "lucid":      {".md", ".txt"},
    "prd":        {".pdf", ".md", ".docx", ".txt"},
    "jenkins":    {".log", ".txt", ".xml", ".json"},
}

MANIFEST_FILE = config.STATE_DIR / "manifest.json"


def load_manifest() -> Dict[str, str]:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: Dict[str, str]) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=1), encoding="utf-8")


def repo_head(repo_dir: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except Exception:
        return ""


def chunk_file(
    source_key: str, source_type: str, path: Path, folder: Path, commit_hash: str
) -> List[Chunk]:
    rel_in_folder = path.relative_to(folder).as_posix()
    if source_key in ("selenium", "playwright"):
        return chunk_code_file(
            path, rel_in_folder, folder.name, source_type, commit_hash
        )
    if source_key == "testcases":
        return chunk_testcases(path, rel_in_folder)
    if source_key == "jira":
        return chunk_jira_file(path, rel_in_folder)
    if source_key in ("docs", "prd"):
        return chunk_doc(path, rel_in_folder, source_type=source_type)
    if source_key == "meetings":
        return chunk_meeting(path, rel_in_folder)
    if source_key == "lucid":
        return chunk_lucidchart(path, rel_in_folder)
    if source_key == "jenkins":
        return chunk_jenkins(path, rel_in_folder)
    return []


def walk_source(source_key: str, folder: Path) -> List[Path]:
    exts = EXTENSIONS[source_key]
    files: List[Path] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        # Folder-root README.md files are drop-zone contracts, not data.
        if path.name.lower() == "readme.md" and path.parent == folder:
            continue
        if path.suffix.lower() in exts:
            files.append(path)
    return files


def ingest_source(source_key: str, manifest: Dict[str, str], full: bool) -> None:
    folder_name, source_type = config.SOURCES[source_key]
    folder = config.DATA_ROOT / folder_name
    if not folder.exists():
        print(f"[{source_key}] folder missing: {folder} — skipped")
        return

    commit_hash = repo_head(folder) if source_key in ("selenium", "playwright") else ""
    files = walk_source(source_key, folder)
    seen: set = set()
    added = skipped = failed = points = 0

    for path in files:
        rel = path.relative_to(config.DATA_ROOT).as_posix()
        seen.add(rel)
        digest = sha256_file(path)
        if not full and manifest.get(rel) == digest:
            skipped += 1
            continue
        try:
            chunks = chunk_file(source_key, source_type, path, folder, commit_hash)
        except Exception as exc:  # keep going: one bad file must not stop a run
            print(f"[{source_key}] ERROR chunking {rel}: {exc}")
            failed += 1
            continue
        if rel in manifest:
            delete_source_path(rel)  # changed file: clear old points first
        try:
            points += upsert_chunks(chunks, rel, digest)
        except Exception as exc:
            print(f"[{source_key}] ERROR upserting {rel}: {exc}")
            failed += 1
            continue
        manifest[rel] = digest
        added += 1

    # Files that disappeared since last run: remove their vectors.
    prefix = folder_name + "/"
    removed = [r for r in list(manifest) if r.startswith(prefix) and r not in seen]
    for rel in removed:
        delete_source_path(rel)
        del manifest[rel]

    print(
        f"[{source_key}] files: {len(files)} | ingested: {added} "
        f"({points} chunks) | unchanged: {skipped} | removed: {len(removed)} "
        f"| errors: {failed}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="QABuddyAI batch ingestion")
    parser.add_argument(
        "--source", default="all",
        help="'all' or comma-separated keys: " + ", ".join(config.SOURCES),
    )
    parser.add_argument(
        "--full", action="store_true",
        help="re-ingest everything, ignoring the content-hash manifest",
    )
    args = parser.parse_args()

    if args.source == "all":
        keys = [k for k in config.SOURCES if k not in config.PHASE2_SOURCES]
    else:
        keys = [k.strip() for k in args.source.split(",") if k.strip()]
        unknown = [k for k in keys if k not in config.SOURCES]
        if unknown:
            parser.error(f"unknown source(s): {unknown}")
        phase2 = [k for k in keys if k in config.PHASE2_SOURCES]
        if phase2:
            print(f"note: {phase2} are phase-2 sources — skipped")
            keys = [k for k in keys if k not in config.PHASE2_SOURCES]

    ensure_collection()
    manifest = load_manifest()
    for key in keys:
        ingest_source(key, manifest, args.full)
        save_manifest(manifest)  # save after each source: crash-safe
    print("done.")


if __name__ == "__main__":
    main()
