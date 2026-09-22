"""Render run results: per-ticket tabs, filters and downloads."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..models import RunResult, Severity, TicketOutcome, TicketResult
from ..services.artifacts import build_ticket_zip, build_zip, ticket_artifacts
from ..services.renderers import (
    render_playwright_md,
    render_requirements_md,
    render_test_cases_csv,
    render_test_cases_md,
    render_test_plan_md,
    render_ticket_result_md,
    render_traceability_csv,
)
from .components import readiness_badge, render_tile_row, source_badge, tile

_OUTCOME_ICON = {
    TicketOutcome.COMPLETED: "🟢",
    TicketOutcome.COMPLETED_WITH_WARNINGS: "⚠️",
    TicketOutcome.PARTIAL: "🟡",
    TicketOutcome.FAILED: "🔴",
}


def render_run(run: RunResult) -> None:
    st.subheader("3 · Results")
    _render_summary(run)

    if not run.results:
        return

    labels = [
        f"{_OUTCOME_ICON.get(r.outcome, '•')} {r.ticket_key}" for r in run.results
    ]
    for tab, result in zip(st.tabs(labels), run.results, strict=False):
        with tab:
            _render_ticket(result)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _humanize_duration(seconds: float | None) -> str:
    """"1m 46s" is read at a glance; "105.52s" has to be divided first."""
    if not seconds:
        return "—"
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, rest = divmod(total, 60)
    return f"{minutes}m {rest:02d}s"


def _run_totals(run: RunResult) -> tuple[int, int, int | None]:
    """Test cases written, specs generated, and requirement coverage percent."""
    cases = automated = covered = requirements = 0
    for result in run.results:
        if result.test_cases:
            cases += len(result.test_cases.test_cases)
        if result.coverage:
            automated += result.coverage.automated_test_cases
            covered += result.coverage.covered_requirements
            requirements += result.coverage.total_requirements
    pct = round(100 * covered / requirements) if requirements else None
    return cases, automated, pct


def _render_verdict(run: RunResult) -> None:
    """Say what happened in one sentence, before showing a single number."""
    total = len(run.results)

    if not run.successful:
        st.error(
            f"Nothing usable came back from {_plural(total, 'ticket')}. "
            "Open the ticket below to see why and what to change.",
            icon="🔴",
        )
        return

    if len(run.completed) == total:
        st.success(
            f"Done — all {_plural(total, 'ticket')} went through every stage. "
            "The requirements analysis, test plan, test cases and Playwright "
            "code are ready below.",
            icon="✅",
        )
        return

    parts = []
    if run.completed:
        parts.append(f"{len(run.completed)} finished completely")
    if run.with_warnings:
        parts.append(f"{len(run.with_warnings)} finished with warnings")
    if run.partial:
        parts.append(f"{len(run.partial)} stopped part-way")
    if run.failed:
        parts.append(f"{len(run.failed)} failed")
    st.warning(
        f"Out of {_plural(total, 'ticket')}: {', '.join(parts)}. "
        "Everything that did finish is kept and downloadable below.",
        icon="⚠️",
    )


def _render_totals(run: RunResult) -> None:
    """Lead with the deliverables, not with the run's bookkeeping."""
    cases, automated, pct = _run_totals(run)
    duration = (
        (run.finished_at - run.started_at).total_seconds()
        if run.started_at and run.finished_at
        else None
    )
    started = (
        run.started_at.strftime("%d %b %Y at %H:%M UTC") if run.started_at else "—"
    )

    render_tile_row(
        [
            tile(
                "Test cases written",
                str(cases),
                f"Across {_plural(len(run.results), 'ticket')}, each with steps "
                "and an expected result.",
            ),
            tile(
                "Playwright specs",
                str(automated),
                "Test cases turned into runnable TypeScript.",
            ),
            tile(
                "Requirement coverage",
                "—" if pct is None else f"{pct}%",
                "Requirements with at least one test case. Counted in Python "
                "from the saved objects, not claimed by the model.",
                muted=pct is None,
            ),
            tile(
                "Time taken",
                _humanize_duration(duration),
                f"Started {started}.",
            ),
        ]
    )


def _render_summary(run: RunResult) -> None:
    _render_verdict(run)
    _render_totals(run)

    left, right = st.columns([1, 3])
    with left:
        if st.button("Build combined ZIP", use_container_width=True):
            st.session_state["zip_bytes"] = build_zip(run)
    with right:
        data = st.session_state.get("zip_bytes")
        if data:
            st.download_button(
                "Download all artifacts (.zip)",
                data=data,
                file_name=f"{run.run_id}.zip",
                mime="application/zip",
                use_container_width=True,
            )
    # The run id is a timestamp, which is not self-explanatory on its own — say
    # so once, here, rather than showing it as a bare number people must decode.
    where = f" · saved in `{run.output_dir}`" if run.output_dir else ""
    st.caption(
        f"Run `{run.run_id}` — named after the date and time it started"
        f"{where}"
    )


def _render_ticket(result: TicketResult) -> None:
    head = st.columns([2, 1, 1, 1])
    head[0].markdown(f"### {result.ticket_key}")
    head[1].markdown(
        source_badge(result.source.value if result.source else "—"),
        unsafe_allow_html=True,
    )
    head[2].markdown(
        readiness_badge(result.automation_readiness.value), unsafe_allow_html=True
    )
    head[3].caption(
        f"{result.duration_seconds}s" if result.duration_seconds else "—"
    )

    if result.issue and result.issue.summary:
        st.caption(result.issue.summary)

    if result.outcome is TicketOutcome.FAILED:
        st.error(result.error or "This ticket failed.")
        _render_run_details(result)
        return

    if result.outcome is TicketOutcome.PARTIAL:
        produced = [
            name
            for name, value in (
                ("Requirements Analysis", result.analysis),
                ("Test Plan", result.test_plan),
                ("Test Cases", result.test_cases),
                ("Playwright", result.playwright),
            )
            if value is not None
        ]
        st.warning(
            f"**Stopped early — {len(produced)} of 4 stages completed.**\n\n"
            f"{result.error}\n\n"
            f"Kept and downloadable: {', '.join(produced)}."
        )

    errors = [i for i in result.validation_issues if i.severity is Severity.ERROR]
    if errors:
        st.warning(
            "Completed with validation errors:\n\n"
            + "\n".join(f"- {i.message}" for i in errors[:6])
        )

    tabs = st.tabs(
        [
            "Requirements Analysis",
            "Test Plan",
            "Test Cases",
            "Playwright",
            "Traceability",
            "Run Details",
        ]
    )

    with tabs[0]:
        _render_analysis(result)
    with tabs[1]:
        _render_plan(result)
    with tabs[2]:
        _render_cases(result)
    with tabs[3]:
        _render_playwright(result)
    with tabs[4]:
        _render_traceability(result)
    with tabs[5]:
        _render_run_details(result)


def _render_analysis(result: TicketResult) -> None:
    if not result.analysis:
        st.info("No analysis was produced.")
        return
    payload = result.analysis.analysis
    cols = st.columns(4)
    cols[0].metric("Requirements", len(result.analysis.all_requirements))
    cols[1].metric("Acceptance criteria", len(payload.acceptance_criteria))
    cols[2].metric("Risks", len(payload.risks))
    cols[3].metric("Missing details", len(payload.missing_information))

    # The full list already appears under "Missing Information" in the document
    # below, which is also what downloads. Repeating it here made the same six
    # bullets show twice on one screen, so this only points at it.
    if payload.missing_information:
        st.warning(
            f"The ticket left out "
            f"{_plural(len(payload.missing_information), 'detail')} the tests "
            "need — see **Missing Information** near the end of the document "
            "below.",
            icon="⚠️",
        )

    markdown = render_requirements_md(result.analysis)
    st.markdown(markdown)
    st.download_button(
        "Download requirements_analysis.md",
        data=markdown,
        file_name="requirements_analysis.md",
        mime="text/markdown",
        key=f"dl_req_{result.ticket_key}",
    )


def _render_plan(result: TicketResult) -> None:
    if not (result.test_plan and result.analysis):
        st.info("No test plan was produced.")
        return
    markdown = render_test_plan_md(result.test_plan, result.analysis)
    st.markdown(markdown)
    st.download_button(
        "Download test_plan.md",
        data=markdown,
        file_name="test_plan.md",
        mime="text/markdown",
        key=f"dl_plan_{result.ticket_key}",
    )


def _render_cases(result: TicketResult) -> None:
    suite = result.test_cases
    if not suite or not suite.test_cases:
        st.info("No test cases were produced.")
        return

    frame = pd.DataFrame(
        [
            {
                "TC ID": tc.id,
                "Title": tc.title,
                "Priority": tc.priority.value,
                "Type": tc.test_type,
                "Automate": tc.automation_candidate.value,
                "Requirements": ", ".join(tc.requirement_ids),
                "AC": ", ".join(tc.acceptance_criteria_ids),
                "Tags": ", ".join(tc.tags),
                "Steps": len(tc.steps),
            }
            for tc in suite.test_cases
        ]
    )

    search = st.text_input(
        "Search test cases", key=f"search_{result.ticket_key}", placeholder="title, id, tag"
    )
    filters = st.columns(4)
    priorities = filters[0].multiselect(
        "Priority", sorted(frame["Priority"].unique()), key=f"pri_{result.ticket_key}"
    )
    types = filters[1].multiselect(
        "Type", sorted(frame["Type"].unique()), key=f"typ_{result.ticket_key}"
    )
    automate = filters[2].multiselect(
        "Automation", sorted(frame["Automate"].unique()), key=f"aut_{result.ticket_key}"
    )
    requirement_ids = sorted(
        {r for tc in suite.test_cases for r in tc.requirement_ids}
    )
    reqs = filters[3].multiselect(
        "Requirement", requirement_ids, key=f"req_{result.ticket_key}"
    )

    view = frame
    if search:
        mask = view.apply(
            lambda row: search.lower() in " ".join(map(str, row.values)).lower(), axis=1
        )
        view = view[mask]
    if priorities:
        view = view[view["Priority"].isin(priorities)]
    if types:
        view = view[view["Type"].isin(types)]
    if automate:
        view = view[view["Automate"].isin(automate)]
    if reqs:
        view = view[view["Requirements"].apply(lambda v: any(r in v for r in reqs))]

    st.caption(f"{len(view)} of {len(frame)} test cases")
    st.dataframe(view, use_container_width=True, hide_index=True)

    with st.expander("Full detail (markdown)"):
        st.markdown(render_test_cases_md(suite, result.ticket_key))

    cols = st.columns(2)
    cols[0].download_button(
        "Download test_cases.md",
        data=render_test_cases_md(suite, result.ticket_key),
        file_name="test_cases.md",
        mime="text/markdown",
        key=f"dl_tcmd_{result.ticket_key}",
    )
    cols[1].download_button(
        "Download test_cases.csv",
        data=render_test_cases_csv(suite, result.ticket_key),
        file_name="test_cases.csv",
        mime="text/csv",
        key=f"dl_tccsv_{result.ticket_key}",
    )


def _render_playwright(result: TicketResult) -> None:
    bundle = result.playwright
    if not bundle:
        st.info("No automation was produced.")
        return

    st.markdown(readiness_badge(bundle.readiness.value), unsafe_allow_html=True)
    if bundle.readiness.value == "NEEDS_CONFIGURATION":
        st.warning(
            "This is a compilable scaffold, not an execution-ready suite. "
            "Supply the missing information below before running it."
        )
    if bundle.missing_information:
        st.error(
            "Missing before these tests can run:\n\n"
            + "\n".join(f"- {m}" for m in bundle.missing_information)
        )

    for spec in bundle.files:
        st.markdown(f"**`{spec.path}`**")
        st.code(spec.content, language="typescript")
        st.download_button(
            f"Download {spec.path.split('/')[-1]}",
            data=spec.content,
            file_name=spec.path.split("/")[-1],
            mime="text/plain",
            key=f"dl_spec_{result.ticket_key}_{spec.path}",
        )

    if bundle.setup_notes:
        with st.expander("Setup notes"):
            st.markdown("\n".join(f"- {n}" for n in bundle.setup_notes))

    st.download_button(
        "Download playwright_tests.md",
        data=render_playwright_md(bundle, result.ticket_key),
        file_name="playwright_tests.md",
        mime="text/markdown",
        key=f"dl_pwmd_{result.ticket_key}",
    )


def _render_traceability(result: TicketResult) -> None:
    report = result.coverage
    if not report:
        st.info("No coverage was computed.")
        return

    cols = st.columns(4)
    cols[0].metric("Requirement coverage", f"{report.requirement_coverage_pct}%")
    cols[1].metric("AC coverage", f"{report.acceptance_criteria_coverage_pct}%")
    cols[2].metric("Test cases", report.total_test_cases)
    cols[3].metric("Automated", report.automated_test_cases)

    st.caption("Coverage is computed in Python from the validated objects.")

    frame = pd.DataFrame(
        [
            {
                "Requirement": row.requirement_id,
                "AC": row.acceptance_criterion_id,
                "Test Cases": ", ".join(row.test_case_ids) or "—",
                "Automated": ", ".join(row.automated_test_case_ids) or "—",
                "Status": row.coverage_status.value,
                "Reason": row.reason,
            }
            for row in report.rows
        ]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)

    if report.orphan_requirements:
        st.warning(
            "Requirements with no test case: " + ", ".join(report.orphan_requirements)
        )
    if report.orphan_test_cases:
        st.warning(
            "Test cases tracing to nothing: " + ", ".join(report.orphan_test_cases)
        )

    st.download_button(
        "Download traceability_matrix.csv",
        data=render_traceability_csv(report),
        file_name="traceability_matrix.csv",
        mime="text/csv",
        key=f"dl_trace_{result.ticket_key}",
    )


def _render_provider_error(result: TicketResult) -> None:
    """The provider's own message, under the app's interpretation of it."""
    if not result.error_detail:
        return
    with st.expander("What the provider actually said"):
        st.caption(
            "The message above is this app reading the error below. When the "
            "two disagree, trust this one. Secrets are redacted."
        )
        st.code(result.error_detail, language="text")


def _render_run_details(result: TicketResult) -> None:
    st.markdown(render_ticket_result_md(result))
    _render_provider_error(result)

    if result.issue:
        with st.expander("Ticket as fetched (read-only)"):
            st.text(result.issue.as_prompt_block())

    try:
        manifest = ticket_artifacts(result).get("manifest.json", "")
    except Exception:
        manifest = ""
    if manifest:
        st.download_button(
            "Download manifest.json",
            data=manifest,
            file_name="manifest.json",
            mime="application/json",
            key=f"dl_man_{result.ticket_key}",
        )
        st.download_button(
            f"Download {result.ticket_key} artifacts (.zip)",
            data=build_ticket_zip(result),
            file_name=f"{result.ticket_key}.zip",
            mime="application/zip",
            key=f"dl_tzip_{result.ticket_key}",
        )
