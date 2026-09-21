"""Deterministic Markdown and CSV rendering."""

from __future__ import annotations

import csv
import io

from jira_qa_crew.models import TEST_PLAN_SECTIONS, RunResult, TicketOutcome, TicketResult
from jira_qa_crew.services.renderers import (
    render_playwright_md,
    render_requirements_md,
    render_run_summary_md,
    render_test_cases_csv,
    render_test_cases_md,
    render_test_plan_md,
    render_traceability_csv,
)
from jira_qa_crew.services.traceability import build_coverage


def test_requirements_markdown_contains_ids_and_evidence(analysis) -> None:
    out = render_requirements_md(analysis)
    assert "REQ-001" in out
    assert "AC-001" in out
    assert "subtotal minus 20%" in out
    assert "Missing Information" in out


def test_requirements_markdown_states_fields_are_not_generated(analysis) -> None:
    assert "read directly from Jira" in render_requirements_md(analysis)


def test_rendering_is_deterministic(analysis) -> None:
    assert render_requirements_md(analysis) == render_requirements_md(analysis)


def test_test_plan_renders_all_twelve_sections(plan, analysis) -> None:
    out = render_test_plan_md(plan, analysis)
    for index, title in enumerate(TEST_PLAN_SECTIONS, start=1):
        assert f"## {index}. {title}" in out


def test_missing_plan_section_is_marked_not_produced(plan, analysis) -> None:
    plan.sections = plan.sections[:5]
    assert "_Not produced._" in render_test_plan_md(plan, analysis)


def test_test_cases_markdown_has_summary_and_detail(suite) -> None:
    out = render_test_cases_md(suite, "QATEST-7")
    assert "| TC ID |" in out
    assert "QATEST-7-TC-001" in out
    assert "Apply SAVE20" in out


def test_pipes_in_content_do_not_break_the_table(suite) -> None:
    suite.test_cases[0].title = "Total | subtotal mismatch"
    out = render_test_cases_md(suite, "QATEST-7")
    assert r"Total \| subtotal mismatch" in out


def test_newlines_in_cells_do_not_break_the_table(suite) -> None:
    suite.test_cases[0].title = "line one\nline two"
    assert "line one<br>line two" in render_test_cases_md(suite, "QATEST-7")


def test_test_cases_csv_is_valid_and_complete(suite) -> None:
    raw = render_test_cases_csv(suite, "QATEST-7")
    rows = list(csv.DictReader(io.StringIO(raw)))

    assert len(rows) == 4
    assert rows[0]["test_case_id"] == "QATEST-7-TC-001"
    assert rows[0]["jira_key"] == "QATEST-7"
    assert "1. Apply SAVE20" in rows[0]["steps"]


def test_traceability_csv_is_valid(analysis, suite, bundle) -> None:
    report = build_coverage(analysis, suite, bundle)
    rows = list(csv.DictReader(io.StringIO(render_traceability_csv(report))))

    assert rows
    assert "coverage_status" in rows[0]


def test_playwright_markdown_flags_a_scaffold(bundle) -> None:
    out = render_playwright_md(bundle, "QATEST-7")
    assert "NEEDS_CONFIGURATION" in out
    assert "not an execution-ready suite" in out
    assert "```typescript" in out


def test_run_summary_counts_outcomes() -> None:
    run = RunResult(
        run_id="RUN-1",
        requested_tickets=["A-1", "A-2"],
        results=[
            TicketResult(ticket_key="A-1", outcome=TicketOutcome.COMPLETED),
            TicketResult(
                ticket_key="A-2", outcome=TicketOutcome.FAILED, error="boom"
            ),
        ],
    )
    out = render_run_summary_md(run)

    assert "Completed: 1" in out
    assert "Failed: 1" in out
    assert "boom" in out
