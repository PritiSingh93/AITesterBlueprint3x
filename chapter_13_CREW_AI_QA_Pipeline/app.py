"""Jira QA Crew - Streamlit entry point.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import streamlit as st

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dotenv import load_dotenv  # noqa: E402

from jira_qa_crew.config import get_config, reset_config_cache  # noqa: E402
from jira_qa_crew.exceptions import JiraQACrewError  # noqa: E402
from jira_qa_crew.jira.gateway import JiraGateway  # noqa: E402
from jira_qa_crew.logging_utils import configure_logging, redact  # noqa: E402
from jira_qa_crew.services.pipeline import run_pipeline  # noqa: E402
from jira_qa_crew.ui import components, results, state  # noqa: E402

# Load .env at the entry point only, so the library stays usable in tests and
# CI where configuration comes from the real environment.
load_dotenv(Path(__file__).resolve().parent / ".env")

st.set_page_config(
    page_title="Jira QA Crew",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_pipeline_area(ticket_keys: list[str]) -> None:
    progress = state.get_progress()
    if not progress:
        return

    st.subheader("2 · Pipeline")
    total_stages = max(len(ticket_keys) * 4, 1)
    done = sum(
        1
        for stages in progress.values()
        for s in stages
        if s.state.value in {"COMPLETED", "WARNING"}
    )
    st.progress(min(done / total_stages, 1.0), text=f"{done}/{total_stages} stages")

    for ticket_key, stages in progress.items():
        st.markdown(f"**{ticket_key}**")
        columns = st.columns(4)
        for column, stage in zip(columns, stages, strict=False):
            with column:
                components.render_stage(stage)


def main() -> None:
    reset_config_cache()
    config = get_config()
    configure_logging(config.log_level)

    components.inject_theme()
    components.render_header(config.app_name)
    components.render_config_status(config)

    raw, mode, submitted, parsed = components.render_ticket_input(config)

    if submitted and parsed.valid:
        state.reset_progress()
        state.set_run_result(None)
        state.set_value("last_error", "")

        # The UI's mode selector overrides the configured default for this run.
        run_config = replace(config, jira_integration_mode=mode)
        gateway = JiraGateway(run_config)

        status = st.status(
            f"Processing {len(parsed.valid)} ticket(s)...", expanded=True
        )
        try:
            with status:
                for key in parsed.valid:
                    st.write(f"Queued {key}")
                run = run_pipeline(
                    parsed.valid,
                    config=run_config,
                    gateway=gateway,
                    on_progress=state.record_progress,
                )
            state.set_run_result(run)
            status.update(
                label=(
                    f"Done: {len(run.completed)} completed, "
                    f"{len(run.with_warnings)} with warnings, "
                    f"{len(run.failed)} failed"
                ),
                state="complete" if run.successful else "error",
            )
        except JiraQACrewError as exc:
            status.update(label="Run failed", state="error")
            state.set_value("last_error", redact(exc))
        except Exception as exc:  # pragma: no cover - last-resort guard
            status.update(label="Run failed", state="error")
            state.set_value("last_error", redact(exc))

    error = state.get("last_error")
    if error:
        st.error(error)

    _render_pipeline_area(parsed.valid or [])

    run = state.get_run_result()
    if run is not None:
        results.render_run(run)
    elif not submitted:
        st.info(
            "Enter one or more Jira ticket IDs above, then run the crew. "
            "Each ticket is analysed in isolation and produces its own "
            "test plan, test cases, traceability matrix and Playwright suite."
        )


state.init_state()
main()
