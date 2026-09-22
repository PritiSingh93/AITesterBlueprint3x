"""Write run artifacts to disk and package them.

Every path segment is sanitized before use, so neither a ticket key nor a
model-proposed filename can escape the output directory.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ..logging_utils import get_logger
from ..models import RunResult, TicketResult
from ..security import sanitize_path_segment, sanitize_relative_path
from .renderers import (
    render_playwright_md,
    render_requirements_md,
    render_run_summary_md,
    render_test_cases_csv,
    render_test_cases_md,
    render_test_plan_md,
    render_traceability_csv,
    render_traceability_md,
)

logger = get_logger("services.artifacts")

MAX_ZIP_BYTES = 48 * 1024 * 1024


def new_run_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"RUN-{stamp}"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _resolve_within(root: Path, relative: str) -> Path:
    """Join and verify the result stays inside ``root``."""
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if not str(candidate).startswith(str(root_resolved)):
        raise ValueError(f"Refusing to write outside the run directory: {relative}")
    return candidate


def ticket_artifacts(result: TicketResult) -> dict[str, str]:
    """Build every artifact for one ticket as ``relative path -> content``."""
    files: dict[str, str] = {}
    key = sanitize_path_segment(result.ticket_key, fallback="ticket")
    slug = key.lower()

    if result.analysis:
        files["requirements_analysis.md"] = render_requirements_md(result.analysis)
        files["requirements_analysis.json"] = json.dumps(
            result.analysis.model_dump(mode="json"), indent=2, ensure_ascii=False
        )
    if result.test_plan and result.analysis:
        files["test_plan.md"] = render_test_plan_md(result.test_plan, result.analysis)
    if result.test_cases:
        files["test_cases.md"] = render_test_cases_md(result.test_cases, key)
        files["test_cases.csv"] = render_test_cases_csv(result.test_cases, key)
    if result.coverage:
        files["traceability_matrix.csv"] = render_traceability_csv(result.coverage)
        files["traceability_matrix.md"] = render_traceability_md(result.coverage)
    if result.playwright:
        files["playwright_tests.md"] = render_playwright_md(result.playwright, key)
        for spec in result.playwright.files:
            safe = sanitize_relative_path(spec.path, fallback=f"tests/{slug}.spec.ts")
            if not safe.startswith(("tests/", "pages/", "fixtures/")):
                safe = f"tests/{Path(safe).name}"
            files[f"playwright/{safe}"] = spec.content

    files["manifest.json"] = json.dumps(
        _ticket_manifest(result, sorted(files)), indent=2, ensure_ascii=False
    )
    return files


def _ticket_manifest(result: TicketResult, file_names: list[str]) -> dict:
    return {
        "ticket_key": result.ticket_key,
        "outcome": result.outcome.value,
        "source": result.source.value if result.source else None,
        "automation_readiness": result.automation_readiness.value,
        "started_at": result.started_at.isoformat() if result.started_at else None,
        "finished_at": result.finished_at.isoformat() if result.finished_at else None,
        "duration_seconds": result.duration_seconds,
        "jira_url": result.issue.url if result.issue else "",
        "counts": {
            "requirements": result.coverage.total_requirements if result.coverage else 0,
            "acceptance_criteria": (
                result.coverage.total_acceptance_criteria if result.coverage else 0
            ),
            "test_cases": result.coverage.total_test_cases if result.coverage else 0,
            "automated_test_cases": (
                result.coverage.automated_test_cases if result.coverage else 0
            ),
        },
        "coverage": {
            "requirement_pct": (
                result.coverage.requirement_coverage_pct if result.coverage else 0.0
            ),
            "acceptance_criteria_pct": (
                result.coverage.acceptance_criteria_coverage_pct
                if result.coverage
                else 0.0
            ),
        },
        "validation_issues": [i.model_dump(mode="json") for i in result.validation_issues],
        "error": result.error,
        "error_detail": result.error_detail,
        "files": file_names,
    }


def persist_run(run: RunResult, output_dir: str | Path) -> Path:
    """Write every artifact for the run and return the run directory."""
    root = Path(output_dir) / sanitize_path_segment(run.run_id, fallback="run")
    root.mkdir(parents=True, exist_ok=True)

    for result in run.results:
        key = sanitize_path_segment(result.ticket_key, fallback="ticket")
        ticket_root = root / key
        files = ticket_artifacts(result)
        for relative, content in files.items():
            _write(_resolve_within(ticket_root, relative), content)
        result.artifact_dir = str(ticket_root)
        result.artifacts = {name: str(ticket_root / name) for name in files}

    _write(root / "run_summary.md", render_run_summary_md(run))
    _write(
        root / "manifest.json",
        json.dumps(
            {
                "run_id": run.run_id,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "requested_tickets": run.requested_tickets,
                "successful": run.successful,
                "tickets": [
                    _ticket_manifest(r, sorted(ticket_artifacts(r))) for r in run.results
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
    )

    run.output_dir = str(root)
    logger.info("Wrote artifacts for %s to %s", run.run_id, root)
    return root


def build_zip(run: RunResult) -> bytes:
    """Package the whole run in memory. Built only when requested."""
    buffer = io.BytesIO()
    total = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{run.run_id}/run_summary.md", render_run_summary_md(run))
        for result in run.results:
            key = sanitize_path_segment(result.ticket_key, fallback="ticket")
            for relative, content in ticket_artifacts(result).items():
                data = content.encode("utf-8")
                total += len(data)
                if total > MAX_ZIP_BYTES:
                    archive.writestr(
                        f"{run.run_id}/TRUNCATED.txt",
                        "Archive exceeded the size limit and was truncated.",
                    )
                    buffer.seek(0)
                    return buffer.getvalue()
                archive.writestr(f"{run.run_id}/{key}/{relative}", data)
    buffer.seek(0)
    return buffer.getvalue()


def build_ticket_zip(result: TicketResult) -> bytes:
    """Package one ticket's artifacts."""
    buffer = io.BytesIO()
    key = sanitize_path_segment(result.ticket_key, fallback="ticket")
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, content in ticket_artifacts(result).items():
            archive.writestr(f"{key}/{relative}", content)
    buffer.seek(0)
    return buffer.getvalue()
