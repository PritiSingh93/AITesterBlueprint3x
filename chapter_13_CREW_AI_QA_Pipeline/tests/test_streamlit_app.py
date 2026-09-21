"""Streamlit UI tests using streamlit.testing.v1.AppTest.

These render the real app. No run is triggered, so no LLM or Jira call happens.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from jira_qa_crew.models import RunResult, TicketOutcome, TicketResult
from jira_qa_crew.services.traceability import build_coverage

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def run_app(**env: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    for key, value in env.items():
        at.session_state[key] = value
    return at.run()


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "test/model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "rest")
    monkeypatch.setenv("JIRA_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_EMAIL", "qa@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "token-value-1234")


def test_app_renders_without_exception(configured) -> None:
    at = run_app()
    assert not at.exception


def test_header_and_subtitle_are_present(configured) -> None:
    at = run_app()
    markdown = " ".join(m.value for m in at.markdown)
    assert "Jira QA Crew" in markdown
    assert "Playwright automation directly from Jira" in markdown


def test_ticket_input_and_mode_selector_exist(configured) -> None:
    at = run_app()
    assert len(at.text_area) >= 1
    assert len(at.selectbox) >= 1
    assert at.selectbox[0].options[0].startswith("Auto")


def test_unconfigured_app_shows_actionable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Set to empty rather than deleting: app.py calls load_dotenv(), which fills
    # in absent keys from a developer's local .env but leaves present ones alone.
    # Empty is also what a half-filled .env actually looks like.
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("GROQ_API_KEY", "")

    at = run_app()

    assert not at.exception
    assert at.error, "missing configuration must be surfaced, not hidden"
    assert any("LLM" in e.value for e in at.error)


def test_run_button_is_disabled_without_tickets(configured) -> None:
    at = run_app()
    assert at.button[0].disabled


def test_invalid_ticket_input_warns_the_user(configured) -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["ticket_input"] = "not-a-ticket"
    at.run()

    assert not at.exception
    assert any("not valid" in w.value.lower() for w in at.warning)


def test_valid_ticket_input_enables_the_run(configured) -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["ticket_input"] = "QATEST-7"
    at.run()

    assert not at.exception
    assert at.button[0].disabled is False


def test_duplicate_tickets_are_reported(configured) -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["ticket_input"] = "QATEST-7, QATEST-7"
    at.run()

    assert any("duplicate" in i.value.lower() for i in at.info)


def _sidebar_labels(at: AppTest) -> str:
    return " ".join(e.label for e in at.get("expander"))


def test_configured_subsystems_show_a_green_indicator(configured) -> None:
    labels = _sidebar_labels(run_app())
    assert "🟢  **LLM** · Ready" in labels
    assert "🟢  **Jira REST** · Ready" in labels


def test_missing_required_llm_shows_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("GROQ_API_KEY", "")

    assert "🔴  **LLM** · Required" in _sidebar_labels(run_app())


def test_unconfigured_mcp_is_optional_not_an_error(configured) -> None:
    """REST covers this run, so MCP must not look like a failure."""
    labels = _sidebar_labels(run_app())
    assert "**Jira MCP**" in labels
    assert "🔴  **Jira MCP**" not in labels


def test_mcp_only_mode_makes_missing_mcp_required(
    configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "mcp")
    assert "🔴  **Jira MCP** · Required" in _sidebar_labels(run_app())


def test_rest_mode_without_credentials_is_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_MODEL", "test/model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "rest")
    monkeypatch.setenv("JIRA_URL", "")
    monkeypatch.setenv("JIRA_EMAIL", "")
    monkeypatch.setenv("JIRA_API_TOKEN", "")

    assert "🔴  **Jira REST** · Required" in _sidebar_labels(run_app())


def test_advanced_settings_show_labelled_values(configured) -> None:
    page = " ".join(m.value for m in run_app().markdown)
    for label in ("Max tickets", "Ticket timeout", "Temperature", "Key pattern"):
        assert label in page


def test_advanced_settings_explain_an_unset_optional_field(configured) -> None:
    """An empty custom field should read as a choice, not as breakage."""
    page = " ".join(m.value for m in run_app().markdown)
    assert "Acceptance criteria field" in page
    assert "read from the description" in page


def test_demo_mode_is_clearly_labelled(
    configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    at = run_app()

    assert any("DEMO MODE" in w.value for w in at.warning)


def test_secrets_are_never_rendered(
    configured, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JIRA_API_TOKEN", "ATATT3xFfGF0supersecrettokenvalue")
    at = run_app()

    page = " ".join(
        [m.value for m in at.markdown]
        + [c.value for c in at.caption]
        + [e.value for e in at.error]
    )
    assert "ATATT3xFfGF0supersecrettokenvalue" not in page


# -- rendering an existing result -------------------------------------------


@pytest.fixture
def completed_run(issue, analysis, plan, suite, bundle) -> RunResult:
    result = TicketResult(
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
    return RunResult(
        run_id="RUN-20260921-101500",
        requested_tickets=["QATEST-7"],
        results=[result],
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )


def test_results_render_from_session_state(configured, completed_run) -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["run_result"] = completed_run
    at.run()

    assert not at.exception
    markdown = " ".join(m.value for m in at.markdown)
    assert "QATEST-7" in markdown


def test_result_metrics_are_shown(configured, completed_run) -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["run_result"] = completed_run
    at.run()

    labels = [m.label for m in at.metric]
    assert "Completed" in labels
    assert "Failed" in labels


def test_downloads_are_offered(configured, completed_run) -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["run_result"] = completed_run
    at.run()

    assert len(at.get("download_button")) >= 1


def test_failed_run_shows_the_error(configured) -> None:
    run = RunResult(
        run_id="RUN-1",
        requested_tickets=["QATEST-7"],
        results=[
            TicketResult(
                ticket_key="QATEST-7",
                outcome=TicketOutcome.FAILED,
                error="Could not fetch QATEST-7 from any provider",
            )
        ],
    )
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["run_result"] = run
    at.run()

    assert not at.exception
    assert any("Could not fetch" in e.value for e in at.error)
