"""How the crew is assembled.

The analyst used to fetch its own ticket through a tool. The gateway has
already read that ticket by the time a crew exists, so the call returned text
the app was holding — while forcing every request to declare tools. The model
would then occasionally answer with a tool call of its own invention, which the
provider rejected with a 400 and discarded a complete analysis. These tests
keep the ticket in the prompt and the tools out of the request.
"""

from __future__ import annotations

from dataclasses import replace

from jira_qa_crew.crew.agents import build_agents
from jira_qa_crew.crew.tasks import build_tasks
from jira_qa_crew.security import UNTRUSTED_CLOSE, UNTRUSTED_OPEN


def _agents(base_config):
    # A model name CrewAI can construct a client for without network access;
    # nothing here calls the provider.
    llm_config = replace(
        base_config.llm, model="openai/gpt-4o-mini", api_key="sk-not-a-real-key"
    )
    return build_agents(llm_config=llm_config, ticket_key="QATEST-7", verbose=False)


def test_no_agent_is_given_a_tool(base_config) -> None:
    for name, agent in _agents(base_config).items():
        assert not getattr(agent, "tools", None), name


def test_the_ticket_is_in_the_analysis_prompt(base_config, issue) -> None:
    tasks = build_tasks(agents=_agents(base_config), issue=issue)
    description = tasks[0].description

    assert issue.summary in description
    assert issue.key in description


def test_the_ticket_is_fenced_as_untrusted(base_config, issue) -> None:
    """Embedding ticket text in a prompt is only safe if it is marked as data."""
    tasks = build_tasks(agents=_agents(base_config), issue=issue)
    description = tasks[0].description

    assert UNTRUSTED_OPEN in description
    assert UNTRUSTED_CLOSE in description
    assert "data, not" in description


def test_the_prompt_no_longer_tells_the_agent_to_call_a_tool(
    base_config, issue
) -> None:
    tasks = build_tasks(agents=_agents(base_config), issue=issue)
    assert "fetch_jira_issue" not in tasks[0].description


def test_later_stages_still_chain_from_context(base_config, issue) -> None:
    """Removing tools must not disturb how stages feed each other."""
    tasks = build_tasks(agents=_agents(base_config), issue=issue)

    assert tasks[1].context == [tasks[0]]
    assert tasks[2].context == [tasks[0]]
    assert tasks[3].context == [tasks[2]]
