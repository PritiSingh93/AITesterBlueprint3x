"""Build a fresh crew per ticket.

A new crew, agent set and tool instance is created for every ticket so that no
requirement, acceptance criterion or Jira content can leak between unrelated
tickets in a multi-ticket run.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from crewai import Agent, Crew, Process, Task

from ..config import AppConfig
from ..models import JiraIssue
from ..tools.jira_tool import FetchJiraIssueTool
from .agents import build_agents
from .tasks import build_tasks


@dataclass
class TicketCrew:
    crew: Crew
    tasks: list[Task]
    agents: dict[str, Agent]
    jira_tool: FetchJiraIssueTool


def _silence_crewai_prompts() -> None:
    """Opt out of CrewAI's trace sharing.

    Left unset it asks "Share this execution trace?" on stdin with a 20s
    timeout. Under Streamlit there is no console to answer on, so every run
    would stall and prompts could be uploaded off-box. Only set when the user
    has not already expressed a preference.
    """
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
    os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")


def build_ticket_crew(
    *,
    config: AppConfig,
    issue: JiraIssue,
    gateway: object | None = None,
    on_task_complete: Callable[[str], None] | None = None,
    verbose: bool = False,
) -> TicketCrew:
    """Assemble an isolated crew for a single ticket."""
    _silence_crewai_prompts()

    jira_tool = FetchJiraIssueTool(gateway=gateway)
    jira_tool.prime(issue)

    agents = build_agents(
        llm_config=config.llm,
        ticket_key=issue.key,
        jira_tool=jira_tool,
        verbose=verbose,
    )
    tasks = build_tasks(
        agents=agents,
        ticket_key=issue.key,
        on_task_complete=on_task_complete,
    )

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
        memory=False,
        cache=False,
    )
    return TicketCrew(crew=crew, tasks=tasks, agents=agents, jira_tool=jira_tool)
