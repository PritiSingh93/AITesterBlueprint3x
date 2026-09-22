"""Task construction and wiring."""

from __future__ import annotations

from collections.abc import Callable

from crewai import Agent, Task

from ..models import (
    AnalysisPayload,
    JiraIssue,
    PlaywrightBundle,
    TestCaseSuite,
    TestPlan,
)
from ..security import INJECTION_GUARD, fence_untrusted
from .prompts import task_prompt


def _slug(ticket_key: str) -> str:
    return ticket_key.lower().replace("_", "-")


def build_tasks(
    *,
    agents: dict[str, Agent],
    issue: JiraIssue,
    on_task_complete: Callable[[str], None] | None = None,
) -> list[Task]:
    """Create the four sequential tasks.

    Each stage's output is passed to later stages as explicit ``context``, and
    each returns a validated Pydantic object rather than free-form markdown.

    The ticket is embedded in the analysis prompt rather than fetched by the
    agent. The gateway has already read it by the time a crew is built, so a
    tool call would only hand back text the app is holding — while requiring
    the request to declare tools, which is what let the model answer with a
    tool call the provider then rejected. No tools also means no tool for
    injected ticket text to aim at.
    """
    ticket_key = issue.key
    values = {
        "ticket_key": ticket_key,
        "ticket_slug": _slug(ticket_key),
        "injection_guard": INJECTION_GUARD,
        "ticket_block": fence_untrusted(issue.as_prompt_block()),
    }

    def callback_for(stage: str) -> Callable[[object], None] | None:
        if on_task_complete is None:
            return None

        def _cb(_output: object) -> None:
            on_task_complete(stage)

        return _cb

    analysis = Task(
        **task_prompt("analysis", **values),
        agent=agents["analyst"],
        output_pydantic=AnalysisPayload,
        callback=callback_for("Jira Analyst"),
    )
    plan = Task(
        **task_prompt("test_plan", **values),
        agent=agents["planner"],
        context=[analysis],
        output_pydantic=TestPlan,
        callback=callback_for("Test Plan Writer"),
    )
    # Context is deliberately narrow. On a provider that meters prompt +
    # max_tokens against one ceiling, every token of inherited context is a
    # token the stage cannot spend on its own answer. Measured: carrying the
    # 12-section plan into this stage cost ~2k prompt tokens and truncated the
    # output. The analysis holds the REQ/AC ids these cases must trace to,
    # which is what the stage actually needs.
    cases = Task(
        **task_prompt("test_cases", **values),
        agent=agents["case_writer"],
        context=[analysis],
        output_pydantic=TestCaseSuite,
        callback=callback_for("Test Case Writer"),
    )
    playwright = Task(
        **task_prompt("playwright", **values),
        agent=agents["coder"],
        context=[cases],
        output_pydantic=PlaywrightBundle,
        callback=callback_for("Playwright Coder"),
    )

    return [analysis, plan, cases, playwright]
