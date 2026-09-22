"""Output-budget clamping.

Groq's free tier meters ``prompt_tokens + max_tokens`` against one per-request
ceiling and returns 413 above it, before any work happens. These tests pin the
arithmetic that keeps every request under that ceiling.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from jira_qa_crew.crew.agents import (
    MIN_MAX_TOKENS,
    STAGE_MAX_TOKENS,
    effective_max_tokens,
)
from jira_qa_crew.services.pipeline import explain_crew_failure


@pytest.fixture
def llm(base_config):
    return base_config.llm


def test_no_ceiling_means_the_budget_is_untouched(llm) -> None:
    config = replace(llm, max_tokens=8000, tpm_limit=0)
    assert effective_max_tokens(config) == 8000


def test_budget_is_clamped_to_fit_the_ceiling(llm) -> None:
    config = replace(llm, max_tokens=8000, tpm_limit=8000, prompt_reserve=4800)
    assert effective_max_tokens(config) == 3200


def test_a_budget_already_under_the_ceiling_is_kept(llm) -> None:
    config = replace(llm, max_tokens=2000, tpm_limit=8000, prompt_reserve=4800)
    assert effective_max_tokens(config) == 2000


def test_clamping_never_returns_an_unusable_budget(llm) -> None:
    """A huge reserve must not clamp the budget to zero."""
    config = replace(llm, max_tokens=4000, tpm_limit=5000, prompt_reserve=4900)
    assert effective_max_tokens(config) == MIN_MAX_TOKENS


def test_every_stage_budget_fits_the_groq_free_tier(llm) -> None:
    config = replace(llm, tpm_limit=8000, prompt_reserve=4800)
    for stage, budget in STAGE_MAX_TOKENS.items():
        effective = effective_max_tokens(config, budget)
        assert effective + config.prompt_reserve <= config.tpm_limit, stage


def test_explicit_request_is_also_clamped(llm) -> None:
    config = replace(llm, tpm_limit=8000, prompt_reserve=4800)
    assert effective_max_tokens(config, 8000) == 3200


# -- error explanation ------------------------------------------------------


def test_413_is_explained_as_a_sizing_problem_not_a_wait() -> None:
    exc = RuntimeError(
        "Error code: 413 - {'error': {'message': 'Request too large for model "
        "`openai/gpt-oss-120b` on tokens per minute (TPM): Limit 8000, "
        "Requested 8791, please reduce your message size'}}"
    )
    message = explain_crew_failure(exc)

    assert "larger than the provider allows" in message
    assert "8791" in message and "8000" in message
    assert "LLM_TPM_LIMIT=8000" in message
    # Waiting does not fix a per-request sizing error.
    assert "wait" not in message.lower()


def test_429_is_still_explained_as_a_rate_limit() -> None:
    message = explain_crew_failure(RuntimeError("Error code: 429 rate limit"))
    assert "rate limited" in message


def test_daily_quota_says_how_long_and_not_to_retry() -> None:
    """Telling someone to "wait a minute" for a 31-minute reset wastes their time."""
    exc = RuntimeError(
        "Error code: 429 - Rate limit reached on tokens per day (TPD): "
        "Limit 200000, Used 198530, Requested 5793. "
        "Please try again in 31m7.535999999s."
    )
    message = explain_crew_failure(exc)

    assert "daily token quota" in message
    assert "31 minutes" in message
    assert "198530" in message and "200000" in message
    assert "Retrying sooner will not help" in message


def test_401_blames_the_key() -> None:
    message = explain_crew_failure(
        RuntimeError("litellm.AuthenticationError: Error code: 401 - invalid api key")
    )
    assert "rejected the API key" in message
    assert "LLM_API_KEY" in message


def test_a_rejected_tool_call_is_explained_not_dumped() -> None:
    """The provider echoes the whole generation back; a banner cannot hold it."""
    payload = '{"name": "JSON", "arguments": {"functional_requirements": [' + (
        '{"id": "REQ-001", "text": "x"},' * 60
    ) + "]}}"
    exc = RuntimeError(
        "Error code: 400 - {'error': {'message': \"Tool call validation failed: "
        "attempted to call tool 'JSON' which was not in request.tools\", "
        f"'code': 'tool_use_failed', 'failed_generation': '{payload}'}}}}"
    )

    message = explain_crew_failure(exc)

    assert "tool call the provider would not accept" in message
    assert "Run Details" in message
    assert len(message) < 400
    assert "REQ-001" not in message


def test_an_unrecognised_error_is_trimmed_for_the_banner() -> None:
    message = explain_crew_failure(RuntimeError("blah " * 400))

    assert len(message) < 400
    assert "full text under Run Details" in message


def test_403_does_not_blame_the_key() -> None:
    """A WAF block in front of the provider is not a credentials problem.

    litellm raises AuthenticationError for 403 too, so keying on the word
    "authentication" sent people to rotate a key that was provably valid while
    the real cause went unnamed.
    """
    message = explain_crew_failure(
        RuntimeError(
            "litellm.AuthenticationError: Error code: 403 - "
            "<html>error code: 1010</html>"
        )
    )

    assert "403" in message
    assert "try the run again" in message
    assert "rejected the API key" not in message


def test_per_minute_limit_suggests_a_short_retry() -> None:
    exc = RuntimeError(
        "Error code: 429 - Rate limit reached on tokens per minute (TPM). "
        "Please try again in 8.5s."
    )
    message = explain_crew_failure(exc)

    assert "8 seconds" in message
    assert "daily" not in message.lower()
