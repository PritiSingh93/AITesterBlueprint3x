"""Configuration loading and startup validation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from jira_qa_crew.config import load_config
from jira_qa_crew.exceptions import ConfigurationError


def test_defaults_are_applied_when_nothing_is_set() -> None:
    config = load_config()
    assert config.app_name == "Jira QA Crew"
    assert config.jira_integration_mode == "auto"
    assert config.pipeline.max_tickets == 20
    assert config.llm.temperature == 0.1


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Custom QA")
    monkeypatch.setenv("PIPELINE_MAX_TICKETS", "5")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")

    config = load_config()

    assert config.app_name == "Custom QA"
    assert config.pipeline.max_tickets == 5
    assert config.llm.temperature == 0.7


def test_model_id_is_never_hard_coded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider naming changes, so the model must come from configuration."""
    monkeypatch.setenv("LLM_MODEL", "anthropic/claude-sonnet-5")
    assert load_config().llm.model == "anthropic/claude-sonnet-5"


def test_reasoning_effort_is_read_and_normalised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_REASONING_EFFORT", "LOW")
    assert load_config().llm.reasoning_effort == "low"


def test_reasoning_effort_defaults_to_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Models without a reasoning mode must not receive the parameter."""
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    assert load_config().llm.reasoning_effort == ""


def test_output_budget_fits_under_a_typical_per_request_ceiling() -> None:
    """prompt + max_tokens must fit, so the budget cannot be near the ceiling."""
    llm = load_config().llm
    assert llm.max_tokens + llm.prompt_reserve <= 8000


def test_jira_email_falls_back_to_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_USERNAME", "qa@example.com")
    assert load_config().rest.email == "qa@example.com"


def test_groq_key_is_accepted_as_the_llm_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_example_key_value")
    assert load_config().llm.api_key == "gsk_example_key_value"


def test_bad_integer_is_reported_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_MAX_TICKETS", "many")
    with pytest.raises(ConfigurationError) as excinfo:
        load_config()
    assert "PIPELINE_MAX_TICKETS" in str(excinfo.value)


def test_bad_json_is_reported_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_MCP_ARGS_JSON", "[not json")
    with pytest.raises(ConfigurationError):
        load_config()


def test_validation_flags_a_missing_llm() -> None:
    problems = load_config().validate()
    assert any("LLM" in p for p in problems)


def test_validation_flags_rest_mode_without_credentials(base_config) -> None:
    config = replace(
        base_config,
        jira_integration_mode="rest",
        rest=replace(base_config.rest, api_token="", email=""),
    )
    assert any("rest" in p.lower() for p in config.validate())


def test_validation_flags_mcp_mode_without_configuration(base_config) -> None:
    config = replace(base_config, jira_integration_mode="mcp")
    assert any("mcp" in p.lower() for p in config.validate())


def test_valid_configuration_has_no_problems(base_config) -> None:
    assert replace(base_config, jira_integration_mode="rest").validate() == []


def test_demo_mode_still_requires_a_model(base_config) -> None:
    """Demo mode fakes Jira, not the crew. The agents still call the provider."""
    config = replace(
        base_config,
        demo_mode=True,
        llm=replace(base_config.llm, api_key=""),
    )
    problems = config.validate()

    assert any("LLM is not configured" in p for p in problems)
    assert any("only Jira is faked" in p for p in problems)


def test_demo_mode_does_not_require_a_jira_provider(base_config) -> None:
    config = replace(
        base_config,
        demo_mode=True,
        rest=replace(base_config.rest, url="", email="", api_token=""),
    )
    assert config.validate() == []


def test_unknown_integration_mode_is_rejected(base_config) -> None:
    config = replace(base_config, jira_integration_mode="carrier-pigeon")
    assert any("JIRA_INTEGRATION_MODE" in p for p in config.validate())


def test_readiness_reports_each_subsystem(base_config) -> None:
    readiness = replace(base_config, jira_integration_mode="rest").readiness()
    assert readiness["llm"] is True
    assert readiness["jira_rest"] is True
    assert readiness["jira_mcp"] is False
