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
from .components import readiness_badge, source_badge

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


def _render_summary(run: RunResult) -> None:
    cols = st.columns(6)
    cols[0].metric("Run", run.run_id.replace("RUN-", ""))
    cols[1].metric("Tickets", len(run.results))
    cols[2].metric("Completed", len(run.completed))
    cols[3].metric("With warnings", len(run.with_warnings))
    cols[4].metric("Partial", len(run.partial))
    cols[5].metric("Failed", len(run.failed))

    if not run.successful:
        st.error("No ticket produced usable output. See the per-ticket errors below.")
    elif run.partial:
        st.warning(
            f"{len(run.partial)} ticket(s) stopped early. The stages that did "
            "finish are complete and downloadable below — only the remaining "
            "stages are missing."
        )
    elif run.failed:
        st.warning(
            f"{len(run.failed)} of {len(run.results)} tickets failed. "
            "The rest completed."
        )

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
    if run.output_dir:
        st.caption(f"Artifacts written to `{run.output_dir}`")


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
    cols[3].metric("Gaps", len(payload.missing_information))

    if payload.missing_information:
        st.warning(
            "Missing information the ticket did not provide:\n\n"
            + "\n".join(f"- {m}" for m in payload.missing_information)
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


def _render_run_details(result: TicketResult) -> None:
    st.markdown(render_ticket_result_md(result))

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
