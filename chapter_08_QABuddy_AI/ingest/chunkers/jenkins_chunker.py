"""Jenkins chunker: one build run = one summary chunk; failed steps / stack
traces isolated as separate high-priority chunks (is_failure=True payload).
300-500 tokens, no overlap, noise (timestamps, ANSI codes) stripped.

Supports JUnit/TestNG XML results and raw console logs. Filename convention:
<job>_<build#>_console.log / <job>_<build#>_results.xml
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

from ingest.chunkers.base import Chunk, read_text, recursive_split

MAX_TOKENS = 500
STACK_LINES = 30  # keep top of stack traces

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_TS = re.compile(r"^\[?\d{4}-\d{2}-\d{2}[T ][\d:.,]+\]?\s*")
_FILENAME = re.compile(r"^(?P<job>.+?)[_\-](?P<build>\d+)[_\-]")
_FAIL_LINE = re.compile(
    r"(FAILED|FAILURE|BUILD FAILED|ERROR\b|Exception\b|Traceback|AssertionError)",
)


def _job_build(path: Path) -> Tuple[str, str]:
    m = _FILENAME.match(path.name)
    if m:
        return m.group("job"), m.group("build")
    return path.stem, ""


def _meta(job: str, build: str, rel_path: str, **extra) -> dict:
    return {
        "job_name": job,
        "build_number": build,
        "file_path": rel_path,
        "source_type": "jenkins",
        **extra,
    }


# --------------------------------------------------------------------------- #
# JUnit / TestNG XML                                                           #
# --------------------------------------------------------------------------- #
def _chunk_results_xml(path: Path, rel_path: str) -> List[Chunk]:
    job, build = _job_build(path)
    root = ET.fromstring(read_text(path))
    cases = root.iter("testcase") if root.tag != "testcase" else [root]

    chunks: List[Chunk] = []
    total = passed = failed = skipped = 0
    failed_names: List[str] = []
    for case in cases:
        total += 1
        name = case.get("name", "?")
        classname = case.get("classname", "")
        full_name = f"{classname}.{name}" if classname else name
        failure = case.find("failure")
        error = case.find("error")
        if case.find("skipped") is not None:
            skipped += 1
            continue
        node = failure if failure is not None else error
        if node is None:
            passed += 1
            continue
        failed += 1
        failed_names.append(full_name)
        message = node.get("message", "") or ""
        trace = "\n".join((node.text or "").strip().splitlines()[:STACK_LINES])
        text = (
            f"FAILED TEST: {full_name}\n"
            f"Job: {job} | Build: {build}\n"
            f"Error: {message}\n{trace}"
        ).strip()
        for piece in recursive_split(text, MAX_TOKENS):
            chunks.append(
                Chunk(
                    text=piece,
                    metadata=_meta(
                        job, build, rel_path,
                        build_status="FAILED",
                        failed_step=full_name,
                        is_failure=True,
                    ),
                )
            )

    status = "FAILED" if failed else "SUCCESS"
    summary = (
        f"Jenkins build summary — Job: {job} | Build: {build} | Status: {status}\n"
        f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}"
    )
    if failed_names:
        summary += "\nFailed tests:\n" + "\n".join(f"- {n}" for n in failed_names[:40])
    chunks.insert(
        0,
        Chunk(text=summary, metadata=_meta(job, build, rel_path, build_status=status)),
    )
    return chunks


# --------------------------------------------------------------------------- #
# Console logs                                                                 #
# --------------------------------------------------------------------------- #
def _clean(line: str) -> str:
    return _TS.sub("", _ANSI.sub("", line)).rstrip()


def _chunk_console_log(path: Path, rel_path: str) -> List[Chunk]:
    job, build = _job_build(path)
    lines = [_clean(l) for l in read_text(path).splitlines()]

    # Failure blocks: context around lines matching failure markers, merged.
    blocks: List[Tuple[int, int]] = []
    for i, line in enumerate(lines):
        if _FAIL_LINE.search(line):
            start, end = max(0, i - 5), min(len(lines), i + STACK_LINES)
            if blocks and start <= blocks[-1][1]:
                blocks[-1] = (blocks[-1][0], max(blocks[-1][1], end))
            else:
                blocks.append((start, end))

    status = "FAILED" if blocks else "SUCCESS"
    chunks: List[Chunk] = []
    head = "\n".join(l for l in lines[:15] if l)
    tail = "\n".join(l for l in lines[-25:] if l)
    summary = (
        f"Jenkins console summary — Job: {job} | Build: {build} | Status: {status}\n"
        f"--- start ---\n{head}\n--- end ---\n{tail}"
    )
    for piece in recursive_split(summary, MAX_TOKENS):
        chunks.append(
            Chunk(text=piece, metadata=_meta(job, build, rel_path, build_status=status))
        )

    for start, end in blocks:
        block = "\n".join(l for l in lines[start:end] if l)
        first_fail = next((l for l in lines[start:end] if _FAIL_LINE.search(l)), "")
        text = f"FAILURE BLOCK — Job: {job} | Build: {build}\n{block}"
        for piece in recursive_split(text, MAX_TOKENS):
            chunks.append(
                Chunk(
                    text=piece,
                    metadata=_meta(
                        job, build, rel_path,
                        build_status="FAILED",
                        failed_step=first_fail[:120],
                        is_failure=True,
                    ),
                )
            )
    return chunks


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #
def chunk_jenkins(path: Path, rel_path: str) -> List[Chunk]:
    if path.suffix.lower() == ".xml":
        try:
            return _chunk_results_xml(path, rel_path)
        except ET.ParseError:
            return _chunk_console_log(path, rel_path)
    return _chunk_console_log(path, rel_path)
