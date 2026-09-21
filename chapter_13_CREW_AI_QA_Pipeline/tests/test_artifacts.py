"""Artifact paths, manifest and ZIP packaging."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime

import pytest

from jira_qa_crew.models import RunResult, TicketOutcome, TicketResult
from jira_qa_crew.services.artifacts import (
    build_ticket_zip,
    build_zip,
    new_run_id,
    persist_run,
    ticket_artifacts,
)
from jira_qa_crew.services.traceability import build_coverage


@pytest.fixture
def result(issue, analysis, plan, suite, bundle) -> TicketResult:
    return TicketResult(
        ticket_key="QATEST-7",
        outcome=TicketOutcome.COMPLETED,
        source=issue.source,
        issue=issue,
        analysis=analysis,
        test_plan=plan,
        test_cases=suite,
        playwright=bundle,
        coverage=build_coverage(analysis, suite, bundle),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )


@pytest.fixture
def run(result) -> RunResult:
    return RunResult(
        run_id=new_run_id(),
        requested_tickets=["QATEST-7"],
        results=[result],
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )


def test_run_id_has_the_expected_shape() -> None:
    assert new_run_id(datetime(2026, 9, 21, 10, 30, 15)).startswith("RUN-20260921-")


def test_every_expected_artifact_is_produced(result) -> None:
    files = ticket_artifacts(result)
    for expected in (
        "requirements_analysis.md",
        "requirements_analysis.json",
        "test_plan.md",
        "test_cases.md",
        "test_cases.csv",
        "traceability_matrix.csv",
        "playwright_tests.md",
        "manifest.json",
    ):
        assert expected in files, expected
    assert any(p.startswith("playwright/tests/") for p in files)


def test_manifest_records_counts_and_coverage(result) -> None:
    manifest = json.loads(ticket_artifacts(result)["manifest.json"])

    assert manifest["ticket_key"] == "QATEST-7"
    assert manifest["counts"]["test_cases"] == 4
    assert manifest["counts"]["requirements"] == 2
    assert manifest["automation_readiness"] == "NEEDS_CONFIGURATION"


def test_persist_writes_the_expected_tree(run, tmp_path) -> None:
    root = persist_run(run, tmp_path)

    assert (root / "run_summary.md").is_file()
    assert (root / "manifest.json").is_file()
    assert (root / "QATEST-7" / "test_plan.md").is_file()
    assert (root / "QATEST-7" / "playwright" / "tests").is_dir()


def test_persist_records_paths_on_the_result(run, tmp_path) -> None:
    persist_run(run, tmp_path)
    assert run.results[0].artifact_dir
    assert "test_plan.md" in run.results[0].artifacts


def test_hostile_spec_path_cannot_escape_the_run_directory(run, tmp_path) -> None:
    """A model-proposed path is untrusted input like any other."""
    run.results[0].playwright.files[0].path = "../../../../evil.ts"

    root = persist_run(run, tmp_path)

    written = [p for p in root.rglob("*") if p.is_file()]
    assert all(str(root.resolve()) in str(p.resolve()) for p in written)
    assert not (tmp_path.parent / "evil.ts").exists()


def test_hostile_ticket_key_is_sanitized(run, tmp_path) -> None:
    run.results[0].ticket_key = "../../escape"
    root = persist_run(run, tmp_path)
    assert all(str(root.resolve()) in str(p.resolve()) for p in root.rglob("*"))


def test_zip_contains_the_run_tree(run) -> None:
    archive = zipfile.ZipFile(io.BytesIO(build_zip(run)))
    names = archive.namelist()

    assert any(n.endswith("run_summary.md") for n in names)
    assert any("QATEST-7/test_cases.csv" in n for n in names)
    assert archive.testzip() is None


def test_ticket_zip_contains_only_that_ticket(result) -> None:
    names = zipfile.ZipFile(io.BytesIO(build_ticket_zip(result))).namelist()
    assert names
    assert all(n.startswith("QATEST-7/") for n in names)


def test_failed_ticket_still_produces_a_manifest() -> None:
    failed = TicketResult(
        ticket_key="QATEST-404", outcome=TicketOutcome.FAILED, error="not found"
    )
    manifest = json.loads(ticket_artifacts(failed)["manifest.json"])
    assert manifest["outcome"] == "FAILED"
    assert manifest["error"] == "not found"
