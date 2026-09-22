"""Application configuration.

Values are read from environment variables, then from ``st.secrets`` when the app
runs under Streamlit. Nothing here imports Streamlit at module scope, so the
orchestration layer stays usable outside the UI (tests, CLI, CI).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from .exceptions import ConfigurationError

SECRET_KEYS: frozenset[str] = frozenset(
    {
        "LLM_API_KEY",
        "JIRA_API_TOKEN",
        "JIRA_BEARER_TOKEN",
        "JIRA_MCP_HEADERS_JSON",
        "GROQ_API_KEY",
        "OPENAI_API_KEY",
    }
)

_TRUE = {"1", "true", "yes", "on"}


def _secrets_lookup(name: str) -> str | None:
    """Read a key from ``st.secrets`` without requiring Streamlit."""
    try:
        import streamlit as st
    except Exception:
        return None
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        # No secrets.toml present, or running outside a Streamlit runtime.
        return None
    return None


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value == "":
        value = _secrets_lookup(name)
    if value is None or value == "":
        return default
    return value.strip()


def _get_bool(name: str, default: bool = False) -> bool:
    raw = get_setting(name, "")
    if not raw:
        return default
    return raw.lower() in _TRUE


def _get_int(name: str, default: int) -> int:
    raw = get_setting(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc


def _get_float(name: str, default: float) -> float:
    raw = get_setting(name, "")
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number, got {raw!r}") from exc


def _get_json(name: str, default: Any) -> Any:
    raw = get_setting(name, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{name} must be valid JSON: {exc}") from exc


@dataclass(frozen=True)
class LLMConfig:
    model: str
    api_key: str
    base_url: str
    temperature: float
    max_tokens: int
    reasoning_effort: str = ""
    # Providers that meter per request count prompt + max_tokens against one
    # ceiling, so an output budget is only safe relative to the prompt size.
    tpm_limit: int = 0
    prompt_reserve: int = 4800

    @property
    def configured(self) -> bool:
        return bool(self.model and self.api_key)


@dataclass(frozen=True)
class JiraRestConfig:
    url: str
    auth_mode: str
    email: str
    api_token: str
    bearer_token: str
    api_version: str
    acceptance_criteria_field: str
    include_comments: bool
    max_comments: int
    timeout_seconds: int

    @property
    def configured(self) -> bool:
        if not self.url:
            return False
        if self.auth_mode == "bearer":
            return bool(self.bearer_token)
        return bool(self.email and self.api_token)


@dataclass(frozen=True)
class JiraMCPConfig:
    transport: str
    url: str
    command: str
    args: list[str]
    headers: dict[str, str]
    env: dict[str, str]
    get_issue_tool: str
    issue_key_argument: str
    timeout_seconds: int
    allowed_tools: frozenset[str]

    @property
    def configured(self) -> bool:
        if self.transport == "stdio":
            return bool(self.command)
        return bool(self.url)


@dataclass(frozen=True)
class PipelineConfig:
    max_tickets: int
    max_retries: int
    ticket_timeout_seconds: int


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_env: str
    output_dir: str
    log_level: str
    demo_mode: bool
    jira_integration_mode: str
    jira_key_pattern: str
    llm: LLMConfig
    rest: JiraRestConfig
    mcp: JiraMCPConfig
    pipeline: PipelineConfig
    warnings: list[str] = field(default_factory=list)

    def readiness(self) -> dict[str, bool]:
        return {
            "llm": self.llm.configured,
            "jira_rest": self.rest.configured,
            "jira_mcp": self.mcp.configured,
            "demo_mode": self.demo_mode,
        }

    def validate(self) -> list[str]:
        """Return actionable configuration problems (empty when usable)."""
        problems: list[str] = []
        if self.jira_integration_mode not in {"auto", "mcp", "rest"}:
            problems.append(
                "JIRA_INTEGRATION_MODE must be one of: auto, mcp, rest "
                f"(got {self.jira_integration_mode!r})."
            )
        # Demo mode substitutes fixtures for Jira. It does not substitute
        # anything for the model: the four agents still do the real work, so a
        # demo deployment without a key would offer a Run button that can only
        # fail once the crew starts.
        if not self.llm.configured:
            problems.append(
                "LLM is not configured. Set LLM_MODEL and LLM_API_KEY "
                "in your environment or .streamlit/secrets.toml. "
                "This is required in demo mode too: only Jira is faked."
            )
        if self.demo_mode:
            return problems
        if self.jira_integration_mode == "rest" and not self.rest.configured:
            problems.append(
                "JIRA_INTEGRATION_MODE=rest but the REST provider is incomplete. "
                "Set JIRA_URL plus JIRA_EMAIL/JIRA_API_TOKEN (basic) "
                "or JIRA_BEARER_TOKEN (bearer)."
            )
        if self.jira_integration_mode == "mcp" and not self.mcp.configured:
            problems.append(
                "JIRA_INTEGRATION_MODE=mcp but the MCP provider is incomplete. "
                "Set JIRA_MCP_URL (http/sse) or JIRA_MCP_COMMAND (stdio)."
            )
        if self.jira_integration_mode == "auto" and not (
            self.rest.configured or self.mcp.configured
        ):
            problems.append(
                "No Jira provider is configured. Configure MCP, REST, or enable "
                "DEMO_MODE=true to explore the app with local fixtures."
            )
        return problems


def _load_mcp_env(rest_url: str, rest_email: str, rest_token: str) -> dict[str, str]:
    """Environment handed to a stdio MCP server subprocess."""
    env = dict(_get_json("JIRA_MCP_ENV_JSON", {}) or {})
    env.setdefault("JIRA_URL", get_setting("JIRA_MCP_JIRA_URL", rest_url))
    env.setdefault("JIRA_USERNAME", get_setting("JIRA_USERNAME", rest_email))
    env.setdefault("JIRA_API_TOKEN", rest_token)
    env.setdefault("PATH", os.environ.get("PATH", ""))
    return {k: v for k, v in env.items() if v}


def load_config() -> AppConfig:
    """Build an :class:`AppConfig` from the current environment."""
    rest_url = get_setting("JIRA_URL", "").rstrip("/")
    rest_email = get_setting("JIRA_EMAIL") or get_setting("JIRA_USERNAME")
    rest_token = get_setting("JIRA_API_TOKEN")

    rest = JiraRestConfig(
        url=rest_url,
        auth_mode=get_setting("JIRA_AUTH_MODE", "basic").lower(),
        email=rest_email,
        api_token=rest_token,
        bearer_token=get_setting("JIRA_BEARER_TOKEN"),
        api_version=get_setting("JIRA_API_VERSION", "3"),
        acceptance_criteria_field=get_setting("JIRA_ACCEPTANCE_CRITERIA_FIELD"),
        include_comments=_get_bool("JIRA_INCLUDE_COMMENTS", False),
        max_comments=_get_int("JIRA_MAX_COMMENTS", 20),
        timeout_seconds=_get_int("JIRA_REST_TIMEOUT_SECONDS", 30),
    )

    mcp = JiraMCPConfig(
        transport=get_setting("JIRA_MCP_TRANSPORT", "stdio").lower(),
        url=get_setting("JIRA_MCP_URL"),
        command=get_setting("JIRA_MCP_COMMAND"),
        args=list(_get_json("JIRA_MCP_ARGS_JSON", []) or []),
        headers=dict(_get_json("JIRA_MCP_HEADERS_JSON", {}) or {}),
        env=_load_mcp_env(rest_url, rest_email, rest_token),
        get_issue_tool=get_setting("JIRA_MCP_GET_ISSUE_TOOL"),
        issue_key_argument=get_setting("JIRA_MCP_ISSUE_KEY_ARG", "issue_key"),
        timeout_seconds=_get_int("JIRA_MCP_TIMEOUT_SECONDS", 20),
        allowed_tools=frozenset(
            t.strip()
            for t in get_setting(
                "JIRA_MCP_ALLOWED_TOOLS", "jira_get_issue,getJiraIssue,get_issue"
            ).split(",")
            if t.strip()
        ),
    )

    llm = LLMConfig(
        model=get_setting("LLM_MODEL"),
        api_key=get_setting("LLM_API_KEY") or get_setting("GROQ_API_KEY"),
        base_url=get_setting("LLM_BASE_URL"),
        temperature=_get_float("LLM_TEMPERATURE", 0.1),
        # Reasoning models spend part of this budget thinking before they emit a
        # token of JSON, so keep reasoning effort low rather than raising this.
        max_tokens=_get_int("LLM_MAX_TOKENS", 3200),
        reasoning_effort=get_setting("LLM_REASONING_EFFORT").lower(),
        tpm_limit=_get_int("LLM_TPM_LIMIT", 0),
        prompt_reserve=_get_int("LLM_PROMPT_RESERVE", 4800),
    )

    pipeline = PipelineConfig(
        max_tickets=_get_int("PIPELINE_MAX_TICKETS", 20),
        max_retries=_get_int("PIPELINE_MAX_RETRIES", 2),
        ticket_timeout_seconds=_get_int("PIPELINE_TICKET_TIMEOUT_SECONDS", 600),
    )

    return AppConfig(
        app_name=get_setting("APP_NAME", "Jira QA Crew"),
        app_env=get_setting("APP_ENV", "development"),
        output_dir=get_setting("OUTPUT_DIR", "outputs"),
        log_level=get_setting("LOG_LEVEL", "INFO").upper(),
        demo_mode=_get_bool("DEMO_MODE", False),
        jira_integration_mode=get_setting("JIRA_INTEGRATION_MODE", "auto").lower(),
        jira_key_pattern=get_setting("JIRA_KEY_PATTERN", r"^[A-Z][A-Z0-9_]+-\d+$"),
        llm=llm,
        rest=rest,
        mcp=mcp,
        pipeline=pipeline,
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return load_config()


def reset_config_cache() -> None:
    get_config.cache_clear()
