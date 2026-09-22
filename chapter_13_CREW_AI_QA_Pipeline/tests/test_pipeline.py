"""Pipeline orchestration: isolation, partial success, failure handling.

CrewAI is faked here. These tests assert orchestration behaviour, not model
quality, and never make a paid request.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from jira_qa_crew.crew.callbacks import STAGE_NAMES
from jira_qa_crew.exceptions import (
    AllProvidersFailedError,
    ConfigurationError,
    JiraTransientError,
)
from jira_qa_crew.models import (
    JiraIssue,
    ProviderSource,
    StageState,
    TicketOutcome,
)
from jira_qa_crew.services import pipeline as pipeline_module
from jira_qa_crew.services.pipeline import run_pipeline


class StubGateway:
    """Returns a distinct issue per key, or raises for keys in ``failures``."""

    def __init__(self, failures: dict[str, Exception] | None = None):
        self.failures = failures or {}
        self.calls: list[str] = []

    def fetch_issue(self, issue_key: str) -> JiraIssue:
        self.calls.append(issue_key)
        if issue_key in self.failures:
            raise self.failures[issue_key]
        return JiraIssue(
            key=issue_key,
            summary=f"Summary for {issue_key}",
            description=f"Body of {issue_key}",
            source=ProviderSource.REST,
        )


class FakeCrew:
    def __init__(self, outputs, on_task_complete, raises=None):
        self._outputs = outputs
        self._cb = on_task_complete
        self._raises = raises

    def kickoff(self):
        if self._raises:
            raise self._raises
        for stage in STAGE_NAMES:
            if self._cb:
                self._cb(stage)
        return _CrewOutput(self._outputs)


class _CrewOutput:
    def __init__(self, tasks_output):
        self.tasks_output = tasks_output
        self.token_usage = None


class FakeTask:
    """Mirrors crewai.Task, which keeps its own output after execution."""

    def __init__(self, output=None):
        self.output = output


class FakeTicketCrew:
    def __init__(self, crew, tasks=None):
        self.crew = crew
        self.tasks = tasks or []


@pytest.fixture
def config(base_config, tmp_path):
    return replace(base_config, output_dir=str(tmp_path), jira_integration_mode="rest")


@pytest.fixture
def stub_crew(monkeypatch, payload, plan, suite, bundle, fake_task_output):
    """Install a fake crew builder and let tests tweak its behaviour."""
    state: dict = {
        "raises": None,
        "outputs": None,
        "seen_tickets": [],
        # Outputs already stored on Task objects when the crew blows up, which
        # is what a real mid-run failure leaves behind.
        "completed_before_failure": [],
    }

    def factory(*, config, issue, gateway, on_task_complete, verbose):
        state["seen_tickets"].append(issue.key)
        outputs = state["outputs"] or [
            fake_task_output(pydantic=payload),
            fake_task_output(pydantic=plan),
            fake_task_output(pydantic=suite),
            fake_task_output(pydantic=bundle),
        ]
        raises = state["raises"]
        if callable(raises):
            raises = raises(issue.key)
        done = state["completed_before_failure"]
        tasks = [FakeTask(o) for o in done] + [
            FakeTask(None) for _ in range(4 - len(done))
        ]
        return FakeTicketCrew(FakeCrew(outputs, on_task_complete, raises), tasks)

    monkeypatch.setattr(pipeline_module, "build_ticket_crew", factory)
    return state


# -- happy path -------------------------------------------------------------


def test_single_ticket_completes_and_produces_every_artifact(config, stub_crew) -> None:
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert run.successful
    result = run.results[0]
    assert result.outcome in (
        TicketOutcome.COMPLETED,
        TicketOutcome.COMPLETED_WITH_WARNINGS,
    )
    assert result.analysis and result.test_plan and result.test_cases
    assert result.playwright and result.coverage
    assert result.source is ProviderSource.REST


def test_artifacts_are_written_to_disk(config, stub_crew, tmp_path) -> None:
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    root = tmp_path / run.run_id
    assert (root / "run_summary.md").is_file()
    assert (root / "QATEST-7" / "test_plan.md").is_file()


def test_all_four_stages_are_reported_complete(config, stub_crew) -> None:
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    states = {s.name: s.state for s in run.results[0].stages}

    assert set(states) == set(STAGE_NAMES)
    assert all(
        state in (StageState.COMPLETED, StageState.WARNING)
        for state in states.values()
    )


def test_progress_hook_receives_updates(config, stub_crew) -> None:
    seen: list[str] = []
    run_pipeline(
        ["QATEST-7"],
        config=config,
        gateway=StubGateway(),
        on_progress=lambda key, tracker: seen.append(key),
    )
    assert "QATEST-7" in seen


# -- multi-ticket behaviour -------------------------------------------------


def test_one_failing_ticket_does_not_stop_the_others(config, stub_crew) -> None:
    gateway = StubGateway(failures={"QATEST-8": JiraTransientError("jira down")})

    run = run_pipeline(["QATEST-7", "QATEST-8", "QATEST-9"], config=config, gateway=gateway)

    outcomes = {r.ticket_key: r.outcome for r in run.results}
    assert outcomes["QATEST-8"] is TicketOutcome.FAILED
    assert outcomes["QATEST-7"] is not TicketOutcome.FAILED
    assert outcomes["QATEST-9"] is not TicketOutcome.FAILED
    assert run.successful, "a run with at least one good ticket is a success"


def test_each_ticket_gets_its_own_crew(config, stub_crew) -> None:
    """Fresh context per ticket is what stops requirements leaking between them."""
    run_pipeline(["QATEST-7", "QATEST-9"], config=config, gateway=StubGateway())
    assert stub_crew["seen_tickets"] == ["QATEST-7", "QATEST-9"]


def test_every_ticket_failing_makes_the_run_unsuccessful(config, stub_crew) -> None:
    gateway = StubGateway(
        failures={
            "QATEST-7": JiraTransientError("down"),
            "QATEST-8": JiraTransientError("down"),
        }
    )
    run = run_pipeline(["QATEST-7", "QATEST-8"], config=config, gateway=gateway)

    assert not run.successful
    assert len(run.failed) == 2


def test_analysis_is_bound_to_the_ticket_it_came_from(config, stub_crew) -> None:
    run = run_pipeline(["QATEST-7", "QATEST-9"], config=config, gateway=StubGateway())
    for result in run.results:
        assert result.analysis.issue.key == result.ticket_key


# -- failure handling -------------------------------------------------------


def test_fetch_failure_is_reported_without_running_the_crew(config, stub_crew) -> None:
    gateway = StubGateway(failures={"QATEST-7": AllProvidersFailedError("QATEST-7", {})})

    run = run_pipeline(["QATEST-7"], config=config, gateway=gateway)

    assert run.results[0].outcome is TicketOutcome.FAILED
    assert stub_crew["seen_tickets"] == [], "no tokens should be spent on a dead ticket"


def test_crew_exception_fails_only_that_ticket(config, stub_crew) -> None:
    stub_crew["raises"] = RuntimeError("model provider exploded")

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert run.results[0].outcome is TicketOutcome.FAILED
    assert "exploded" in run.results[0].error


def test_the_providers_own_words_survive_the_explanation(config, stub_crew) -> None:
    """The friendly message is a guess; the raw error is the evidence.

    A 403 from the network in front of the provider was being reported as
    rejected credentials. Without the original text there was nothing in the
    run to contradict it.
    """
    stub_crew["raises"] = RuntimeError(
        "litellm.AuthenticationError: Error code: 403 - error code: 1010"
    )

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    result = run.results[0]

    assert "403" in result.error
    assert "error code: 1010" in result.error_detail


def test_the_raw_error_is_redacted_before_it_is_kept(config, stub_crew) -> None:
    """Provider errors echo request headers, so this sink must not leak a key."""
    stub_crew["raises"] = RuntimeError(
        "401 unauthorized: Authorization=Bearer "
        "gsk_b1234567890abcdefghijABCDEFGHIJ1234567890abcdefgh"
    )

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    detail = run.results[0].error_detail

    assert "gsk_" not in detail
    assert "REDACTED" in detail


def test_error_detail_is_empty_on_success(config, stub_crew) -> None:
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    assert run.results[0].error_detail == ""


def test_failed_ticket_marks_remaining_stages_failed(config, stub_crew) -> None:
    stub_crew["raises"] = RuntimeError("boom")
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert all(s.state is StageState.FAILED for s in run.results[0].stages)


def test_unparseable_stage_output_fails_the_ticket(
    config, stub_crew, fake_task_output
) -> None:
    stub_crew["outputs"] = [fake_task_output(raw="I give up")] * 4

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert run.results[0].outcome is TicketOutcome.FAILED
    assert "did not return valid" in run.results[0].error


def test_too_few_task_outputs_is_partial_not_failed(
    config, stub_crew, fake_task_output, payload
) -> None:
    """Fewer outputs than stages still leaves the analysis worth keeping."""
    stub_crew["outputs"] = [fake_task_output(pydantic=payload)]

    result = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway()).results[0]

    assert result.outcome is TicketOutcome.PARTIAL
    assert result.analysis is not None
    assert result.playwright is None


def test_a_ticket_is_never_successful_without_its_outputs(config, stub_crew) -> None:
    stub_crew["raises"] = RuntimeError("boom")
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    result = run.results[0]
    assert result.outcome is TicketOutcome.FAILED
    assert result.test_cases is None and result.playwright is None


# -- partial results --------------------------------------------------------


def test_work_finished_before_a_failure_is_kept(
    config, stub_crew, fake_task_output, payload, plan, suite
) -> None:
    """The exact case that lost three stages of real output to a quota error."""
    stub_crew["completed_before_failure"] = [
        fake_task_output(pydantic=payload),
        fake_task_output(pydantic=plan),
        fake_task_output(pydantic=suite),
    ]
    stub_crew["raises"] = RuntimeError("Error code: 429 - daily quota exhausted")

    result = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway()).results[0]

    assert result.outcome is TicketOutcome.PARTIAL
    assert result.analysis is not None, "analysis must survive"
    assert result.test_plan is not None, "test plan must survive"
    assert result.test_cases is not None, "test cases must survive"
    assert result.playwright is None, "the stage that never ran stays empty"
    assert "quota" in result.error


def test_partial_ticket_still_writes_its_artifacts(
    config, stub_crew, fake_task_output, payload, plan, suite, tmp_path
) -> None:
    stub_crew["completed_before_failure"] = [
        fake_task_output(pydantic=payload),
        fake_task_output(pydantic=plan),
        fake_task_output(pydantic=suite),
    ]
    stub_crew["raises"] = RuntimeError("Error code: 429 - daily quota exhausted")

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    root = tmp_path / run.run_id / "QATEST-7"

    assert (root / "requirements_analysis.md").is_file()
    assert (root / "test_plan.md").is_file()
    assert (root / "test_cases.csv").is_file()
    assert not (root / "playwright_tests.md").exists()


def test_partial_counts_as_a_usable_run(
    config, stub_crew, fake_task_output, payload, plan
) -> None:
    stub_crew["completed_before_failure"] = [
        fake_task_output(pydantic=payload),
        fake_task_output(pydantic=plan),
    ]
    stub_crew["raises"] = RuntimeError("boom")

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert run.successful, "artifacts exist, so the run is not a total loss"
    assert len(run.partial) == 1
    assert run.failed == []


def test_partial_is_never_reported_as_completed(
    config, stub_crew, fake_task_output, payload, plan, suite
) -> None:
    stub_crew["completed_before_failure"] = [
        fake_task_output(pydantic=payload),
        fake_task_output(pydantic=plan),
        fake_task_output(pydantic=suite),
    ]
    stub_crew["raises"] = RuntimeError("boom")

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert run.completed == []
    assert run.with_warnings == []


def test_coverage_is_computed_for_a_partial_ticket(
    config, stub_crew, fake_task_output, payload, plan, suite
) -> None:
    """Traceability is still useful without the automation stage."""
    stub_crew["completed_before_failure"] = [
        fake_task_output(pydantic=payload),
        fake_task_output(pydantic=plan),
        fake_task_output(pydantic=suite),
    ]
    stub_crew["raises"] = RuntimeError("boom")

    result = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway()).results[0]

    assert result.coverage is not None
    assert result.coverage.total_test_cases == 4
    assert result.coverage.automated_test_cases == 0


def test_failure_with_nothing_finished_is_still_failed(config, stub_crew) -> None:
    stub_crew["completed_before_failure"] = []
    stub_crew["raises"] = RuntimeError("died immediately")

    result = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway()).results[0]

    assert result.outcome is TicketOutcome.FAILED
    assert result.analysis is None


# -- validation surfacing ---------------------------------------------------


def test_validation_warnings_downgrade_to_completed_with_warnings(
    config, stub_crew, plan, fake_task_output, payload, suite, bundle
) -> None:
    plan.scenarios[0].requirement_ids = ["REQ-404"]
    stub_crew["outputs"] = [
        fake_task_output(pydantic=payload),
        fake_task_output(pydantic=plan),
        fake_task_output(pydantic=suite),
        fake_task_output(pydantic=bundle),
    ]

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert run.results[0].outcome is TicketOutcome.COMPLETED_WITH_WARNINGS
    assert any(
        i.code == "unknown_scenario_ref" for i in run.results[0].validation_issues
    )


def test_ready_claim_with_placeholders_is_downgraded(
    config, stub_crew, fake_task_output, payload, plan, suite, bundle
) -> None:
    from jira_qa_crew.models import AutomationReadiness

    bundle.readiness = AutomationReadiness.READY
    bundle.files[0].content += "\nconst URL = 'TODO';\n"
    stub_crew["outputs"] = [
        fake_task_output(pydantic=payload),
        fake_task_output(pydantic=plan),
        fake_task_output(pydantic=suite),
        fake_task_output(pydantic=bundle),
    ]

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())

    assert (
        run.results[0].playwright.readiness is AutomationReadiness.NEEDS_CONFIGURATION
    ), "the UI must never call a scaffold runnable"


# -- configuration ----------------------------------------------------------


def test_truncation_error_is_explained_with_the_fix(config, stub_crew) -> None:
    """A raw usage dump tells a user nothing; the numbers in it tell them a lot."""
    stub_crew["raises"] = RuntimeError(
        "Could not parse response content as the length limit was reached - "
        "CompletionUsage(completion_tokens=4000, prompt_tokens=4464, "
        "total_tokens=8464, reasoning_tokens=2784)"
    )

    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    error = run.results[0].error

    assert "ran out of output budget" in error
    assert "2784" in error and "1216" in error, "spent vs usable must be spelled out"
    assert "LLM_REASONING_EFFORT=low" in error
    assert "CompletionUsage" not in error, "raw provider dump must not leak to the UI"


def test_rate_limit_error_is_explained(config, stub_crew) -> None:
    stub_crew["raises"] = RuntimeError("Error code: 429 - rate limit exceeded")
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    assert "rate limited" in run.results[0].error


def test_auth_error_points_at_the_right_setting(config, stub_crew) -> None:
    stub_crew["raises"] = RuntimeError("Error code: 401 - Invalid API Key")
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    assert "LLM_API_KEY" in run.results[0].error


def test_unknown_error_is_still_surfaced(config, stub_crew) -> None:
    stub_crew["raises"] = RuntimeError("something nobody anticipated")
    run = run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
    assert "something nobody anticipated" in run.results[0].error


def test_unconfigured_llm_is_rejected_before_any_work(base_config, tmp_path) -> None:
    config = replace(
        base_config,
        output_dir=str(tmp_path),
        llm=replace(base_config.llm, api_key=""),
    )
    with pytest.raises(ConfigurationError):
        run_pipeline(["QATEST-7"], config=config, gateway=StubGateway())
