"""End-to-end checks.

The demo smoke test runs in the default suite: it uses the real fixture
provider, the real validation, traceability and artifact code, and only fakes
the LLM. The tests marked ``integration`` need real credentials and are
deselected by default (``pytest -m "not integration"``).
"""

from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

from jira_qa_crew.config import load_config
from jira_qa_crew.crew.callbacks import STAGE_NAMES
from jira_qa_crew.jira.gateway import JiraGateway
from jira_qa_crew.models import TicketOutcome
from jira_qa_crew.services import pipeline as pipeline_module
from jira_qa_crew.services.pipeline import run_pipeline
from jira_qa_crew.tickets import parse_ticket_input


class _Crew:
    def __init__(self, outputs, cb):
        self._outputs = outputs
        self._cb = cb

    def kickoff(self):
        for stage in STAGE_NAMES:
            self._cb(stage)
        return type("Out", (), {"tasks_output": self._outputs, "token_usage": None})()


class _TicketCrew:
    def __init__(self, crew):
        self.crew = crew


def test_demo_smoke_produces_a_complete_artifact_set(
    monkeypatch, tmp_path, payload, plan, suite, bundle, fake_task_output
) -> None:
    """Real fixtures, real validation, real artifacts; only the LLM is faked."""
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("LLM_MODEL", "test/model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    config = replace(load_config(), output_dir=str(tmp_path))
    assert config.demo_mode is True

    def factory(*, config, issue, gateway, on_task_complete, verbose):
        outputs = [
            fake_task_output(pydantic=payload),
            fake_task_output(pydantic=plan),
            fake_task_output(pydantic=suite),
            fake_task_output(pydantic=bundle),
        ]
        return _TicketCrew(_Crew(outputs, on_task_complete))

    monkeypatch.setattr(pipeline_module, "build_ticket_crew", factory)

    tickets = parse_ticket_input("QATEST-7").valid
    run = run_pipeline(tickets, config=config, gateway=JiraGateway(config))

    assert run.successful
    result = run.results[0]
    assert result.outcome is not TicketOutcome.FAILED
    assert result.source.value == "FIXTURE", "demo output must be labelled FIXTURE"

    root = tmp_path / run.run_id
    for relative in (
        "run_summary.md",
        "manifest.json",
        "QATEST-7/requirements_analysis.md",
        "QATEST-7/test_plan.md",
        "QATEST-7/test_cases.md",
        "QATEST-7/test_cases.csv",
        "QATEST-7/traceability_matrix.csv",
        "QATEST-7/playwright_tests.md",
        "QATEST-7/manifest.json",
    ):
        assert (root / relative).is_file(), relative

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["successful"] is True
    assert manifest["tickets"][0]["ticket_key"] == "QATEST-7"

    spec_files = list((root / "QATEST-7" / "playwright").rglob("*.spec.ts"))
    assert spec_files, "a Playwright spec should be written to disk"
    assert "@playwright/test" in spec_files[0].read_text(encoding="utf-8")


def test_multi_ticket_demo_keeps_artifacts_separate(
    monkeypatch, tmp_path, payload, plan, suite, bundle, fake_task_output
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("LLM_MODEL", "test/model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    config = replace(load_config(), output_dir=str(tmp_path))

    def factory(*, config, issue, gateway, on_task_complete, verbose):
        outputs = [
            fake_task_output(pydantic=payload),
            fake_task_output(pydantic=plan),
            fake_task_output(pydantic=suite),
            fake_task_output(pydantic=bundle),
        ]
        return _TicketCrew(_Crew(outputs, on_task_complete))

    monkeypatch.setattr(pipeline_module, "build_ticket_crew", factory)

    run = run_pipeline(
        ["QATEST-7", "QATEST-9"], config=config, gateway=JiraGateway(config)
    )
    root = tmp_path / run.run_id

    assert (root / "QATEST-7").is_dir()
    assert (root / "QATEST-9").is_dir()
    for result in run.results:
        assert result.analysis.issue.key == result.ticket_key


# ---------------------------------------------------------------------------
# Opt-in live tests
# ---------------------------------------------------------------------------

_LIVE_JIRA = bool(os.getenv("JIRA_URL") and os.getenv("JIRA_API_TOKEN"))
_LIVE_TICKET = os.getenv("INTEGRATION_TICKET_KEY", "")


@pytest.mark.integration
@pytest.mark.skipif(
    not (_LIVE_JIRA and _LIVE_TICKET),
    reason="set JIRA_URL, JIRA_API_TOKEN and INTEGRATION_TICKET_KEY to run",
)
def test_live_jira_rest_fetch() -> None:
    from jira_qa_crew.jira.rest_provider import JiraRestProvider

    config = load_config()
    issue = JiraRestProvider(config.rest).fetch_issue(_LIVE_TICKET)

    assert issue.key == _LIVE_TICKET.upper()
    assert issue.summary


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("JIRA_MCP_COMMAND") and not os.getenv("JIRA_MCP_URL"),
    reason="set JIRA_MCP_COMMAND or JIRA_MCP_URL to run",
)
def test_live_mcp_health() -> None:
    from jira_qa_crew.jira.mcp_provider import JiraMCPProvider

    health = JiraMCPProvider(load_config().mcp).health_check()
    assert health.healthy, health.detail


@pytest.mark.integration
@pytest.mark.skipif(
    not (os.getenv("LLM_API_KEY") and _LIVE_JIRA and _LIVE_TICKET),
    reason="set LLM_API_KEY, Jira credentials and INTEGRATION_TICKET_KEY to run",
)
def test_live_full_pipeline(tmp_path) -> None:
    """Costs real tokens. Never part of the default suite."""
    config = replace(load_config(), output_dir=str(tmp_path))
    run = run_pipeline([_LIVE_TICKET], config=config)

    assert run.successful
    assert (tmp_path / run.run_id / "run_summary.md").is_file()
