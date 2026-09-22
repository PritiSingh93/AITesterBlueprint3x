"""Pipeline orchestration.

One isolated CrewAI run per ticket, sequential inside a ticket and
continue-on-error between tickets, so one bad ticket never costs the whole run.
"""

from __future__ import annotations

import concurrent.futures
import re
from collections.abc import Callable
from datetime import UTC, datetime

from ..config import AppConfig, get_config
from ..crew.callbacks import STAGE_NAMES, ProgressTracker
from ..crew.factory import build_ticket_crew
from ..exceptions import (
    AllProvidersFailedError,
    ConfigurationError,
    JiraError,
    StructuredOutputError,
    TicketTimeoutError,
)
from ..jira.gateway import JiraGateway
from ..logging_utils import get_logger, redact
from ..models import (
    AnalysisPayload,
    AutomationReadiness,
    JiraIssue,
    PlaywrightBundle,
    RequirementAnalysis,
    RunResult,
    Severity,
    StageState,
    TestCaseSuite,
    TestPlan,
    TicketOutcome,
    TicketResult,
    ValidationIssue,
)
from . import validation
from .artifacts import new_run_id, persist_run
from .structured import extract_model
from .traceability import build_coverage

logger = get_logger("services.pipeline")

ProgressHook = Callable[[str, ProgressTracker], None]

_STAGE_MODELS = (
    ("Jira Analyst", AnalysisPayload),
    ("Test Plan Writer", TestPlan),
    ("Test Case Writer", TestCaseSuite),
    ("Playwright Coder", PlaywrightBundle),
)


def run_pipeline(
    ticket_keys: list[str],
    *,
    config: AppConfig | None = None,
    gateway: JiraGateway | None = None,
    on_progress: ProgressHook | None = None,
    verbose: bool = False,
) -> RunResult:
    """Process each ticket in isolation and return the aggregated run."""
    cfg = config or get_config()
    problems = cfg.validate()
    if problems:
        raise ConfigurationError(" ".join(problems))

    gw = gateway or JiraGateway(cfg)
    run = RunResult(
        run_id=new_run_id(),
        requested_tickets=list(ticket_keys),
        started_at=datetime.now(UTC),
    )

    for ticket_key in ticket_keys:
        tracker = ProgressTracker(ticket_key, on_update=on_progress)
        result = _process_ticket(
            ticket_key, cfg, gw, tracker, verbose=verbose
        )
        run.results.append(result)

    run.finished_at = datetime.now(UTC)

    try:
        persist_run(run, cfg.output_dir)
    except Exception as exc:
        logger.exception("Could not write artifacts for %s", run.run_id)
        for result in run.results:
            result.validation_issues.append(
                ValidationIssue(
                    stage="artifacts",
                    severity=Severity.WARNING,
                    code="persist_failed",
                    message=f"Artifacts were not written to disk: {redact(exc)}",
                )
            )

    logger.info(
        "Run %s finished: %s completed, %s with warnings, %s failed",
        run.run_id,
        len(run.completed),
        len(run.with_warnings),
        len(run.failed),
    )
    return run


def _process_ticket(
    ticket_key: str,
    config: AppConfig,
    gateway: JiraGateway,
    tracker: ProgressTracker,
    *,
    verbose: bool,
) -> TicketResult:
    result = TicketResult(
        ticket_key=ticket_key, started_at=datetime.now(UTC)
    )

    # 1. Fetch deterministically before spending any tokens. A bad key or a dead
    #    provider should cost a second, not a full crew run.
    tracker.start("Jira Analyst", "Fetching ticket")
    try:
        issue: JiraIssue = gateway.fetch_issue(ticket_key)
    except (AllProvidersFailedError, JiraError) as exc:
        message = redact(exc)
        tracker.fail_remaining(message)
        result.error = message
        result.outcome = TicketOutcome.FAILED
        result.stages = tracker.snapshot()
        result.finished_at = datetime.now(UTC)
        logger.warning("Fetch failed for %s: %s", ticket_key, message)
        return result

    result.issue = issue
    result.source = issue.source
    tracker.start("Jira Analyst", f"Analysing ticket from {issue.source.value}")

    # 2. Run the crew.
    def advance(stage_name: str) -> None:
        tracker.finish(stage_name)
        index = STAGE_NAMES.index(stage_name)
        if index + 1 < len(STAGE_NAMES):
            tracker.start(STAGE_NAMES[index + 1])

    ticket_crew = None
    crew_error = ""
    crew_error_detail = ""
    outputs: list = []
    try:
        ticket_crew = build_ticket_crew(
            config=config,
            issue=issue,
            gateway=gateway,
            on_task_complete=advance,
            verbose=verbose,
        )
        crew_output = _kickoff_with_timeout(
            ticket_crew.crew, config.pipeline.ticket_timeout_seconds, ticket_key
        )
        outputs = list(getattr(crew_output, "tasks_output", []) or [])
    except ConfigurationError as exc:
        return _fail(result, tracker, redact(exc))
    except TicketTimeoutError as exc:
        crew_error = redact(exc)
    except Exception as exc:
        logger.exception("Crew failed for %s", ticket_key)
        crew_error = explain_crew_failure(exc)
        # The explanation is a guess at what the provider meant. Keep the
        # provider's own words too: when the guess is wrong, this is the only
        # thing that shows it, and a finished run leaves no other trace.
        crew_error_detail = redact(exc)[:2000]

    # A later stage failing does not invalidate the stages that already
    # finished. Their output is real work the user paid for, so it is kept and
    # shown rather than discarded with the error.
    if crew_error:
        outputs = _salvage_outputs(ticket_crew)
        tracker.fail_remaining(crew_error)

    if not outputs:
        return _fail(
            result,
            tracker,
            crew_error or "The crew produced no output.",
            detail=crew_error_detail,
        )

    # 3. Recover and validate whichever stages did produce output.
    issues: list[ValidationIssue] = []
    analysis = plan = suite = bundle = None
    stage_error = ""

    try:
        payload, warns = extract_model(outputs[0], AnalysisPayload, stage="analysis")
        _record_warnings(issues, "analysis", warns)
        analysis = RequirementAnalysis(issue=issue, analysis=payload)
        issues += validation.validate_analysis(payload)

        if len(outputs) > 1:
            plan, warns = extract_model(outputs[1], TestPlan, stage="test_plan")
            _record_warnings(issues, "test_plan", warns)
            issues += validation.validate_test_plan(plan, analysis)

        if len(outputs) > 2:
            suite, warns = extract_model(outputs[2], TestCaseSuite, stage="test_cases")
            _record_warnings(issues, "test_cases", warns)
            issues += validation.validate_test_cases(suite, analysis)

        if len(outputs) > 3:
            bundle, warns = extract_model(
                outputs[3], PlaywrightBundle, stage="playwright"
            )
            _record_warnings(issues, "playwright", warns)
            if suite is not None:
                issues += validation.validate_playwright(bundle, suite)
    except StructuredOutputError as exc:
        stage_error = redact(exc)

    if analysis is None:
        return _fail(result, tracker, stage_error or crew_error)

    # A READY claim with placeholders still in the code is downgraded here, so
    # the UI never tells a user a scaffold is runnable.
    if bundle is not None and any(i.code == "readiness_overclaim" for i in issues):
        bundle.readiness = AutomationReadiness.NEEDS_CONFIGURATION

    coverage = build_coverage(analysis, suite, bundle)
    issues += validation.validate_coverage(coverage)

    result.analysis = analysis
    result.test_plan = plan
    result.test_cases = suite
    result.playwright = bundle
    result.coverage = coverage
    result.validation_issues = issues

    incomplete = bundle is None or crew_error or stage_error
    if incomplete:
        kept = sum(x is not None for x in (analysis, plan, suite, bundle))
        result.outcome = TicketOutcome.PARTIAL
        result.error = crew_error or stage_error
        result.error_detail = crew_error_detail
        logger.info("%s -> PARTIAL (%s/4 stages kept)", ticket_key, kept)
    else:
        tracker.finish(
            STAGE_NAMES[-1],
            StageState.WARNING if issues else StageState.COMPLETED,
        )
        result.outcome = (
            TicketOutcome.COMPLETED_WITH_WARNINGS if issues else TicketOutcome.COMPLETED
        )
        if validation.has_errors(issues):
            result.error = "; ".join(
                i.message for i in issues if i.severity is Severity.ERROR
            )[:500]
        logger.info("%s -> %s", ticket_key, result.outcome.value)

    result.stages = tracker.snapshot()
    result.finished_at = datetime.now(UTC)
    return result


def _salvage_outputs(ticket_crew) -> list:
    """Collect the outputs of tasks that finished before the crew failed.

    CrewAI stores each task's result on the Task itself, so a mid-run failure
    does not destroy the work already done. Stages run in order, so collection
    stops at the first task with no output.
    """
    if ticket_crew is None:
        return []
    salvaged: list = []
    for task in getattr(ticket_crew, "tasks", None) or []:
        output = getattr(task, "output", None)
        if output is None:
            break
        salvaged.append(output)
    return salvaged


_TRUNCATED = ("length limit was reached", "could not parse response content")
# Keyed on the size wording only: a 429 rate limit also mentions "tokens per
# minute", but waiting fixes that one and resizing does not.
_TOO_LARGE = ("request too large", "413")
_RATE_LIMITED = ("rate limit", "429", "too many requests")
# Only a 401 means the key itself was rejected. litellm raises
# AuthenticationError for 403 as well, so matching "authentication" alone sends
# people to check a key that is provably fine while the real cause — a WAF or
# edge block in front of the provider, or an account restriction — goes unnamed.
_AUTH_FAILED = ("401", "invalid api key", "invalid_api_key", "unauthorized")
_FORBIDDEN = ("403", "error code: 1010", "cloudflare", "forbidden")
_TOOL_CALL_REJECTED = ("tool_use_failed", "tool call validation failed")


def explain_crew_failure(exc: Exception) -> str:
    """Turn a provider error into something a user can act on.

    Providers report truncation as a raw usage dump, which says nothing about
    what to change. The numbers in it do, so they are read out here.
    """
    raw = redact(exc)
    lowered = raw.lower()

    if any(token in lowered for token in _TRUNCATED):
        budget = re.search(r"completion_tokens=(\d+)", raw)
        reasoning = re.search(r"reasoning_tokens=(\d+)", raw)
        parts = ["The model ran out of output budget before it finished its JSON."]
        if budget and reasoning:
            spent, thought = int(budget.group(1)), int(reasoning.group(1))
            usable = max(spent - thought, 0)
            parts.append(
                f"It used {spent} output tokens, {thought} of them on internal "
                f"reasoning, leaving only {usable} for the answer."
            )
        parts.append(
            "Fix: set LLM_REASONING_EFFORT=low in .env (reasoning is billed "
            "against the output budget), and/or raise LLM_MAX_TOKENS."
        )
        return " ".join(parts)

    # Checked before the generic rate-limit case: a 413 names a TPM limit but
    # is a per-request sizing problem, and waiting will not fix it.
    if any(token in lowered for token in _TOO_LARGE):
        limit = re.search(r"Limit (\d+)", raw)
        requested = re.search(r"Requested (\d+)", raw)
        parts = ["The request was larger than the provider allows per call."]
        if limit and requested:
            parts.append(
                f"It asked for {requested.group(1)} tokens against a "
                f"{limit.group(1)} limit. That total is prompt + LLM_MAX_TOKENS, "
                "so the output budget must leave room for the prompt."
            )
        parts.append(
            f"Fix: set LLM_TPM_LIMIT={limit.group(1) if limit else '8000'} in .env "
            "so budgets are clamped automatically, or lower LLM_MAX_TOKENS."
        )
        return " ".join(parts)

    if any(token in lowered for token in _RATE_LIMITED):
        retry = re.search(r"try again in ([\dhms.]+)", raw, re.IGNORECASE)
        wait = _humanize_wait(retry.group(1)) if retry else ""

        # Providers word a daily cap differently: "tokens per day", "TPD",
        # "daily quota". All of them mean waiting is the only option.
        if any(token in lowered for token in ("per day", "tpd", "daily")):
            used = re.search(r"Used (\d+)", raw)
            limit = re.search(r"Limit (\d+)", raw)
            quota = (
                f" You have used {used.group(1)} of {limit.group(1)} tokens today."
                if used and limit
                else ""
            )
            return (
                "The daily token quota for this model is exhausted."
                + quota
                + (f" It resets in about {wait}." if wait else "")
                + " Retrying sooner will not help; wait for the reset or upgrade "
                "the provider plan."
            )

        return (
            "The provider rate limited this run."
            + (f" Retry in about {wait}." if wait else " Retry shortly.")
            + " Processing fewer tickets at once also helps."
        )

    if any(token in lowered for token in _AUTH_FAILED):
        return (
            "The model provider rejected the API key. Check LLM_API_KEY and "
            "LLM_BASE_URL in .env."
        )

    if any(token in lowered for token in _TOOL_CALL_REJECTED):
        return (
            "The model wrapped its answer in a tool call the provider would not "
            "accept, so the provider discarded the answer. The text it generated "
            "is under Run Details. Re-running the ticket usually clears it."
        )

    if any(token in lowered for token in _FORBIDDEN):
        return (
            "The model provider refused the request (HTTP 403). This is usually "
            "the network or WAF in front of the provider rather than your key, "
            "so try the run again before changing .env. If it keeps happening, "
            "check that the account still has access to the model and see the "
            "provider's own message under Run Details."
        )

    # An unrecognised provider error can be thousands of characters of echoed
    # request JSON. The banner has to stay readable, so it is trimmed here; the
    # whole thing is kept verbatim in TicketResult.error_detail.
    summary = " ".join(raw.split())
    if len(summary) > 300:
        summary = summary[:300].rstrip() + "… (full text under Run Details)"
    return f"Crew execution failed: {summary}"


def _humanize_wait(raw: str) -> str:
    """Turn a provider's "31m7.535999999s" into "31 minutes"."""
    minutes = re.search(r"(\d+)m", raw)
    if minutes:
        return f"{minutes.group(1)} minutes"
    hours = re.search(r"(\d+)h", raw)
    if hours:
        return f"{hours.group(1)} hours"
    seconds = re.search(r"(\d+)(?:\.\d+)?s", raw)
    if seconds:
        return f"{seconds.group(1)} seconds"
    return ""


def _record_warnings(
    issues: list[ValidationIssue], stage: str, warnings: list[str]
) -> None:
    for message in warnings:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.WARNING,
                code="structured_output_repaired",
                message=message,
            )
        )


def _fail(
    result: TicketResult,
    tracker: ProgressTracker,
    message: str,
    *,
    detail: str = "",
) -> TicketResult:
    tracker.fail_remaining(message)
    result.error = message
    result.error_detail = detail
    result.outcome = TicketOutcome.FAILED
    result.stages = tracker.snapshot()
    result.finished_at = datetime.now(UTC)
    return result


def _kickoff_with_timeout(crew, timeout_seconds: int, ticket_key: str):
    """Run ``crew.kickoff`` with a wall-clock budget.

    Python cannot forcibly kill the worker, so on timeout the run is abandoned
    and reported as failed while the thread may still be winding down. The
    ticket is never reported as successful in that case.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(crew.kickoff)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise TicketTimeoutError(
                f"{ticket_key} exceeded its {timeout_seconds}s budget."
            ) from exc
