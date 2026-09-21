"""Deterministic provider selection and fallback.

Which provider serves a ticket is decided here, in application code. No LLM ever
chooses, and a failed live integration never silently degrades to demo data.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import AppConfig
from ..exceptions import (
    AllProvidersFailedError,
    JiraAuthError,
    JiraError,
    JiraNotFoundError,
    JiraPermissionError,
    JiraProviderUnavailableError,
)
from ..logging_utils import get_logger, redact
from ..models import JiraIssue
from .base import HealthStatus, JiraProvider
from .fixture_provider import JiraFixtureProvider
from .mcp_provider import JiraMCPProvider
from .rest_provider import JiraRestProvider

logger = get_logger("jira.gateway")

# Failures that mean "this ticket will not load from anywhere", so trying the
# other provider only wastes time and produces a more confusing error.
_TERMINAL = (JiraNotFoundError, JiraPermissionError)


@dataclass
class GatewayHealth:
    mode: str
    mcp: HealthStatus
    rest: HealthStatus


class JiraGateway:
    """Fetch an issue using the configured provider strategy."""

    def __init__(
        self,
        config: AppConfig,
        *,
        mcp_provider: JiraProvider | None = None,
        rest_provider: JiraProvider | None = None,
        fixture_provider: JiraProvider | None = None,
    ) -> None:
        self._config = config
        self._mcp = mcp_provider or JiraMCPProvider(config.mcp)
        self._rest = rest_provider or JiraRestProvider(
            config.rest, max_retries=config.pipeline.max_retries
        )
        self._fixture = fixture_provider or JiraFixtureProvider()

    @property
    def mode(self) -> str:
        return self._config.jira_integration_mode

    def _chain(self) -> list[JiraProvider]:
        if self._config.demo_mode:
            return [self._fixture]
        if self.mode == "mcp":
            return [self._mcp]
        if self.mode == "rest":
            return [self._rest]
        return [self._mcp, self._rest]

    def fetch_issue(self, issue_key: str) -> JiraIssue:
        """Return the issue, or raise with every provider's reason."""
        failures: dict[str, str] = {}

        for provider in self._chain():
            if not provider.configured:
                failures[provider.name] = "not configured"
                logger.info("Skipping %s for %s: not configured", provider.name, issue_key)
                continue
            try:
                return provider.fetch_issue(issue_key)
            except _TERMINAL as exc:
                # Authoritative answer: the ticket is unreadable, full stop.
                failures[provider.name] = redact(exc)
                raise AllProvidersFailedError(issue_key, failures) from exc
            except JiraAuthError as exc:
                failures[provider.name] = redact(exc)
                logger.warning("%s auth failed for %s", provider.name, issue_key)
            except (JiraProviderUnavailableError, JiraError) as exc:
                failures[provider.name] = redact(exc)
                logger.warning(
                    "%s failed for %s: %s", provider.name, issue_key, redact(exc)
                )
            except Exception as exc:  # defensive: never crash the whole run
                failures[provider.name] = redact(exc)
                logger.exception("%s raised unexpectedly for %s", provider.name, issue_key)

        raise AllProvidersFailedError(issue_key, failures)

    def health(self) -> GatewayHealth:
        return GatewayHealth(
            mode="demo" if self._config.demo_mode else self.mode,
            mcp=self._mcp.health_check(),
            rest=self._rest.health_check(),
        )
