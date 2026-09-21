"""Render validated objects into Markdown, CSV and TypeScript.

Rendering is deterministic Python. The model's own prose is never the source of
truth for an artifact, so the same validated object always produces the same
file.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from ..models import (
    TEST_PLAN_SECTIONS,
    CoverageReport,
    JiraIssue,
    PlaywrightBundle,
    RequirementAnalysis,
    RunResult,
    TestCaseSuite,
    TestPlan,
    TicketResult,
)


def _fmt_list(values: list[str], empty: str = "_None recorded._") -> str:
    if not values:
        return empty
    return "\n".join(f"- {v}" for v in values)


def _ts(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S UTC") if value else "-"


def _cell(value: str) -> str:
    """Escape a value for use inside a Markdown table cell."""
    return (value or "").replace("|", "\\|").replace("\n", "<br>").strip()


# --------------------------------------------------------------------------
# Requirements analysis
# --------------------------------------------------------------------------


def render_requirements_md(analysis: RequirementAnalysis) -> str:
    issue: JiraIssue = analysis.issue
    payload = analysis.analysis
    out: list[str] = [
        f"# Requirements Analysis - {issue.key}",
        "",
        f"**Summary:** {issue.summary or '_none_'}",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Ticket | {_cell(issue.key)} |",
        f"| Type | {_cell(issue.issue_type)} |",
        f"| Status | {_cell(issue.status)} |",
        f"| Priority | {_cell(issue.priority)} |",
        f"| Labels | {_cell(', '.join(issue.labels) or 'None')} |",
        f"| Components | {_cell(', '.join(issue.components) or 'None')} |",
        f"| Parent | {_cell(issue.parent or 'None')} |",
        f"| Subtasks | {_cell(', '.join(issue.subtasks) or 'None')} |",
        f"| Linked issues | {_cell(', '.join(issue.linked_issues) or 'None')} |",
        f"| Source | {issue.source.value} |",
        f"| Fetched | {_ts(issue.fetched_at)} |",
        f"| URL | {_cell(issue.url or 'n/a')} |",
        "",
        "> Ticket fields above are read directly from Jira, not generated.",
        "",
    ]

    def req_table(title: str, rows: list) -> None:
        out.extend([f"## {title}", ""])
        if not rows:
            out.extend(["_None identified._", ""])
            return
        out.extend(
            ["| ID | Requirement | Classification | Evidence |", "| --- | --- | --- | --- |"]
        )
        for r in rows:
            out.append(
                f"| {_cell(r.id)} | {_cell(r.text)} | {r.classification.value} "
                f"| {_cell(r.evidence) or '-'} |"
            )
        out.append("")

    req_table("Functional Requirements", payload.functional_requirements)
    req_table("Non-Functional Requirements", payload.non_functional_requirements)

    out.extend(["## Acceptance Criteria", ""])
    if payload.acceptance_criteria:
        out.extend(
            [
                "| ID | Criterion | Requirements | Classification |",
                "| --- | --- | --- | --- |",
            ]
        )
        for ac in payload.acceptance_criteria:
            out.append(
                f"| {_cell(ac.id)} | {_cell(ac.text)} "
                f"| {_cell(', '.join(ac.requirement_ids) or '-')} "
                f"| {ac.classification.value} |"
            )
        out.append("")
    else:
        out.extend(["_None identified._", ""])

    for title, values in (
        ("Business Rules", payload.business_rules),
        ("Dependencies", payload.dependencies),
        ("Constraints", payload.constraints),
        ("Risks", payload.risks),
        ("Assumptions", payload.assumptions),
        ("Missing Information", payload.missing_information),
        ("Open Questions", payload.open_questions),
    ):
        out.extend([f"## {title}", "", _fmt_list(values), ""])

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------
# Test plan
# --------------------------------------------------------------------------


def render_test_plan_md(plan: TestPlan, analysis: RequirementAnalysis) -> str:
    issue = analysis.issue
    out: list[str] = [
        f"# Test Plan - {issue.key}",
        "",
        f"**Feature:** {issue.summary or '_none_'}  ",
        f"**Test Plan ID:** TP-{issue.key}  ",
        f"**Generated:** {_ts(issue.fetched_at)}  ",
        f"**Jira source:** {issue.source.value}",
        "",
    ]

    by_number = {s.number: s for s in plan.sections}
    for index in range(1, 13):
        section = by_number.get(index)
        title = section.title if section else TEST_PLAN_SECTIONS[index - 1]
        out.extend([f"## {index}. {title}", ""])
        out.extend([section.content.strip() if section else "_Not produced._", ""])

    out.extend(["## Scenario Traceability", ""])
    if plan.scenarios:
        out.extend(
            [
                "| Scenario | Title | Requirements | Acceptance Criteria |",
                "| --- | --- | --- | --- |",
            ]
        )
        for sc in plan.scenarios:
            out.append(
                f"| {_cell(sc.id)} | {_cell(sc.title)} "
                f"| {_cell(', '.join(sc.requirement_ids) or '-')} "
                f"| {_cell(', '.join(sc.acceptance_criteria_ids) or '-')} |"
            )
        out.append("")
    else:
        out.extend(["_No scenarios recorded._", ""])

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------
# Test cases
# --------------------------------------------------------------------------


def render_test_cases_md(suite: TestCaseSuite, ticket_key: str) -> str:
    out: list[str] = [f"# Test Cases - {ticket_key}", ""]
    if not suite.test_cases:
        out.append("_No test cases were produced._")
        return "\n".join(out) + "\n"

    out.extend(
        [
            f"**Total:** {len(suite.test_cases)}",
            "",
            "| TC ID | Title | Priority | Type | Requirements | AC | Automate |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for tc in suite.test_cases:
        out.append(
            f"| {_cell(tc.id)} | {_cell(tc.title)} | {tc.priority.value} "
            f"| {_cell(tc.test_type)} "
            f"| {_cell(', '.join(tc.requirement_ids) or '-')} "
            f"| {_cell(', '.join(tc.acceptance_criteria_ids) or '-')} "
            f"| {tc.automation_candidate.value} |"
        )
    out.append("")

    out.extend(["---", "", "## Detailed Test Cases", ""])
    for tc in suite.test_cases:
        out.extend(
            [
                f"### {tc.id} - {tc.title}",
                "",
                f"- **Objective:** {tc.objective or '-'}",
                f"- **Priority:** {tc.priority.value}",
                f"- **Type:** {tc.test_type}",
                f"- **Requirements:** {', '.join(tc.requirement_ids) or '-'}",
                f"- **Acceptance Criteria:** "
                f"{', '.join(tc.acceptance_criteria_ids) or '-'}",
                f"- **Automation:** {tc.automation_candidate.value}"
                + (f" - {tc.automation_rationale}" if tc.automation_rationale else ""),
                f"- **Tags:** {', '.join(tc.tags) or '-'}",
                "",
                "**Preconditions**",
                "",
                _fmt_list(tc.preconditions, "_None._"),
                "",
                "**Test Data**",
                "",
                _fmt_list(tc.test_data, "_None specified._"),
                "",
                "**Steps**",
                "",
            ]
        )
        if tc.steps:
            out.extend(["| # | Action | Expected |", "| --- | --- | --- |"])
            for step in tc.steps:
                out.append(
                    f"| {step.number} | {_cell(step.action)} "
                    f"| {_cell(step.expected) or '-'} |"
                )
        else:
            out.append("_No steps recorded._")
        out.extend(
            [
                "",
                f"**Expected Result:** {tc.expected_result or '-'}",
                "",
            ]
        )
        if tc.assumptions_or_blockers:
            out.extend(
                ["**Assumptions / Blockers**", "", _fmt_list(tc.assumptions_or_blockers), ""]
            )
        out.extend(["---", ""])

    return "\n".join(out).rstrip() + "\n"


def render_test_cases_csv(suite: TestCaseSuite, ticket_key: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "test_case_id",
            "jira_key",
            "title",
            "objective",
            "priority",
            "test_type",
            "requirement_ids",
            "acceptance_criteria_ids",
            "preconditions",
            "test_data",
            "steps",
            "expected_result",
            "automation_candidate",
            "automation_rationale",
            "tags",
            "assumptions_or_blockers",
        ]
    )
    for tc in suite.test_cases:
        steps = " | ".join(
            f"{s.number}. {s.action}" + (f" -> {s.expected}" if s.expected else "")
            for s in tc.steps
        )
        writer.writerow(
            [
                tc.id,
                ticket_key,
                tc.title,
                tc.objective,
                tc.priority.value,
                tc.test_type,
                "; ".join(tc.requirement_ids),
                "; ".join(tc.acceptance_criteria_ids),
                "; ".join(tc.preconditions),
                "; ".join(tc.test_data),
                steps,
                tc.expected_result,
                tc.automation_candidate.value,
                tc.automation_rationale,
                "; ".join(tc.tags),
                "; ".join(tc.assumptions_or_blockers),
            ]
        )
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Traceability
# --------------------------------------------------------------------------


def render_traceability_csv(report: CoverageReport) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "requirement_id",
            "acceptance_criterion_id",
            "test_case_ids",
            "automated_test_case_ids",
            "coverage_status",
            "reason",
        ]
    )
    for row in report.rows:
        writer.writerow(
            [
                row.requirement_id,
                row.acceptance_criterion_id,
                "; ".join(row.test_case_ids),
                "; ".join(row.automated_test_case_ids),
                row.coverage_status.value,
                row.reason,
            ]
        )
    return buffer.getvalue()


def render_traceability_md(report: CoverageReport) -> str:
    out = [
        "# Traceability Matrix",
        "",
        f"- Requirements covered: {report.covered_requirements}/"
        f"{report.total_requirements} ({report.requirement_coverage_pct}%)",
        f"- Acceptance criteria covered: {report.covered_acceptance_criteria}/"
        f"{report.total_acceptance_criteria} "
        f"({report.acceptance_criteria_coverage_pct}%)",
        f"- Test cases: {report.total_test_cases} "
        f"({report.automated_test_cases} automated)",
        "",
        "| Requirement | AC | Test Cases | Automated | Status | Reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        out.append(
            f"| {_cell(row.requirement_id)} | {_cell(row.acceptance_criterion_id)} "
            f"| {_cell(', '.join(row.test_case_ids) or '-')} "
            f"| {_cell(', '.join(row.automated_test_case_ids) or '-')} "
            f"| {row.coverage_status.value} | {_cell(row.reason)} |"
        )
    out.append("")
    if report.orphan_requirements:
        out.extend(
            ["## Orphan Requirements", "", _fmt_list(report.orphan_requirements), ""]
        )
    if report.orphan_test_cases:
        out.extend(["## Orphan Test Cases", "", _fmt_list(report.orphan_test_cases), ""])
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------
# Playwright
# --------------------------------------------------------------------------


def render_playwright_md(bundle: PlaywrightBundle, ticket_key: str) -> str:
    out: list[str] = [
        f"# Playwright Automation - {ticket_key}",
        "",
        f"**Readiness:** {bundle.readiness.value}",
        "",
    ]
    if bundle.readiness.value == "NEEDS_CONFIGURATION":
        out.extend(
            [
                "> This is a compilable scaffold, not an execution-ready suite. "
                "Supply the missing information below before running it.",
                "",
            ]
        )

    out.extend(["## Coverage", ""])
    if bundle.mappings:
        out.extend(
            [
                "| Test Case | Test Name | Requirements | AC |",
                "| --- | --- | --- | --- |",
            ]
        )
        for m in bundle.mappings:
            out.append(
                f"| {_cell(m.test_case_id)} | {_cell(m.test_name)} "
                f"| {_cell(', '.join(m.requirement_ids) or '-')} "
                f"| {_cell(', '.join(m.acceptance_criteria_ids) or '-')} |"
            )
        out.append("")
    else:
        out.extend(["_No automated mappings recorded._", ""])

    out.extend(["## Generated Files", ""])
    if bundle.files:
        for file in bundle.files:
            out.extend([f"### `{file.path}`", "", "```typescript", file.content.strip(), "```", ""])
    else:
        out.extend(["_No files generated._", ""])

    for title, values in (
        ("Setup Notes", bundle.setup_notes),
        ("Missing Information", bundle.missing_information),
        ("Assumptions", bundle.assumptions),
    ):
        out.extend([f"## {title}", "", _fmt_list(values), ""])

    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------
# Run summary
# --------------------------------------------------------------------------


def render_run_summary_md(run: RunResult) -> str:
    out = [
        "# Run Summary",
        "",
        f"**Run ID:** {run.run_id}  ",
        f"**Started:** {_ts(run.started_at)}  ",
        f"**Finished:** {_ts(run.finished_at)}",
        "",
        f"- Tickets requested: {len(run.requested_tickets)}",
        f"- Completed: {len(run.completed)}",
        f"- Completed with warnings: {len(run.with_warnings)}",
        f"- Failed: {len(run.failed)}",
        "",
        "| Ticket | Outcome | Source | Automation | Tests | Coverage | Duration |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in run.results:
        coverage = (
            f"{result.coverage.requirement_coverage_pct}%" if result.coverage else "-"
        )
        tests = str(result.coverage.total_test_cases) if result.coverage else "-"
        duration = (
            f"{result.duration_seconds}s" if result.duration_seconds is not None else "-"
        )
        out.append(
            f"| {_cell(result.ticket_key)} | {result.outcome.value} "
            f"| {result.source.value if result.source else '-'} "
            f"| {result.automation_readiness.value} | {tests} | {coverage} "
            f"| {duration} |"
        )
    out.append("")

    failures = run.failed
    if failures:
        out.extend(["## Failures", ""])
        for result in failures:
            out.append(f"- **{result.ticket_key}**: {result.error}")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def render_ticket_result_md(result: TicketResult) -> str:
    """Compact per-ticket run detail, used in the Run Details tab."""
    out = [
        f"# Run Details - {result.ticket_key}",
        "",
        f"- Outcome: {result.outcome.value}",
        f"- Source: {result.source.value if result.source else '-'}",
        f"- Duration: {result.duration_seconds or '-'}s",
        "",
        "## Stages",
        "",
        "| Stage | State | Duration | Message |",
        "| --- | --- | --- | --- |",
    ]
    for stage in result.stages:
        out.append(
            f"| {_cell(stage.name)} | {stage.state.value} "
            f"| {stage.duration_seconds if stage.duration_seconds is not None else '-'} "
            f"| {_cell(stage.message)} |"
        )
    out.append("")
    if result.validation_issues:
        out.extend(["## Validation", "", "| Severity | Stage | Message |", "| --- | --- | --- |"])
        for issue in result.validation_issues:
            out.append(
                f"| {issue.severity.value} | {_cell(issue.stage)} "
                f"| {_cell(issue.message)} |"
            )
        out.append("")
    return "\n".join(out).rstrip() + "\n"
