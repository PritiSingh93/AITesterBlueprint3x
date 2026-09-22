"""Agent construction."""

from __future__ import annotations

from crewai import LLM, Agent

from ..config import LLMConfig
from ..exceptions import ConfigurationError
from .prompts import agent_prompt

# Output budget per stage. Later stages carry more context in their prompt, so
# a bigger prompt leaves less room for the answer, not more.
STAGE_MAX_TOKENS: dict[str, int] = {
    "analyst": 4800,
    "planner": 4000,
    "case_writer": 4800,
    "coder": 4800,
}

MIN_MAX_TOKENS = 1200


def effective_max_tokens(config: LLMConfig, requested: int | None = None) -> int:
    """Clamp the output budget so prompt + output fits a per-request ceiling.

    Groq's free tier rejects a request when ``prompt_tokens + max_tokens``
    exceeds its TPM limit, with a 413 before any work happens. Sizing the
    output budget against the largest expected prompt avoids that entirely.
    """
    budget = requested or config.max_tokens
    if config.tpm_limit:
        headroom = config.tpm_limit - config.prompt_reserve
        budget = min(budget, max(headroom, MIN_MAX_TOKENS))
    return max(budget, MIN_MAX_TOKENS)


def build_llm(config: LLMConfig, *, max_tokens: int | None = None) -> LLM:
    """Build a CrewAI LLM from configuration.

    The model id is never hard-coded: provider naming changes, and a wrong
    literal is a silent production failure.
    """
    if not config.model:
        raise ConfigurationError("LLM_MODEL is not set.")
    if not config.api_key:
        raise ConfigurationError("LLM_API_KEY is not set.")

    kwargs: dict[str, object] = {
        "model": config.model,
        "api_key": config.api_key,
        "temperature": config.temperature,
        "max_tokens": effective_max_tokens(config, max_tokens),
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    if config.reasoning_effort:
        # On a reasoning model, internal thinking is billed against the output
        # budget. Left unconstrained it can consume most of it and truncate the
        # JSON mid-structure, which surfaces as an unparseable response.
        kwargs["reasoning_effort"] = config.reasoning_effort
    return LLM(**kwargs)


def build_agents(
    *,
    llm_config: LLMConfig,
    ticket_key: str,
    verbose: bool = False,
) -> dict[str, Agent]:
    """Create the four pipeline agents.

    Each agent gets its own LLM so its output budget can be sized for its own
    prompt. No agent is given a tool: the ticket is fetched deterministically
    before the crew runs and embedded in the analysis prompt, so nothing here
    needs to reach Jira. See :func:`..crew.tasks.build_tasks`.
    """
    values = {"ticket_key": ticket_key}

    def llm_for(stage: str) -> LLM:
        return build_llm(llm_config, max_tokens=STAGE_MAX_TOKENS[stage])

    analyst = Agent(
        **agent_prompt("jira_analyst", **values),
        llm=llm_for("analyst"),
        verbose=verbose,
        allow_delegation=False,
        max_iter=6,
        max_retry_limit=1,
    )
    planner = Agent(
        **agent_prompt("test_plan_writer", **values),
        llm=llm_for("planner"),
        verbose=verbose,
        allow_delegation=False,
        max_iter=3,
        max_retry_limit=1,
    )
    case_writer = Agent(
        **agent_prompt("test_case_writer", **values),
        llm=llm_for("case_writer"),
        verbose=verbose,
        allow_delegation=False,
        max_iter=3,
        max_retry_limit=1,
    )
    coder = Agent(
        **agent_prompt("playwright_coder", **values),
        llm=llm_for("coder"),
        verbose=verbose,
        allow_delegation=False,
        max_iter=3,
        max_retry_limit=1,
    )

    return {
        "analyst": analyst,
        "planner": planner,
        "case_writer": case_writer,
        "coder": coder,
    }
