"""Typed exceptions for the Jira QA Crew application."""

from __future__ import annotations


class JiraQACrewError(Exception):
    """Base class for every error raised by this application."""


class ConfigurationError(JiraQACrewError):
    """Configuration is missing or invalid."""


class TicketInputError(JiraQACrewError):
    """The user supplied ticket input that cannot be used."""


class JiraError(JiraQACrewError):
    """Base class for Jira integration failures."""


class JiraAuthError(JiraError):
    """Authentication failed (401)."""


class JiraPermissionError(JiraError):
    """Authenticated but not permitted to read the issue (403)."""


class JiraNotFoundError(JiraError):
    """The issue does not exist or is not visible (404)."""


class JiraRateLimitError(JiraError):
    """Jira rejected the request due to rate limiting (429)."""


class JiraTransientError(JiraError):
    """A transient failure worth retrying (timeout, 5xx, connection reset)."""


class JiraProviderUnavailableError(JiraError):
    """A provider is disabled or could not be reached at all."""


class JiraResponseError(JiraError):
    """The provider replied, but the payload was unusable."""


class AllProvidersFailedError(JiraError):
    """Every configured provider failed."""

    def __init__(self, ticket_key: str, failures: dict[str, str]) -> None:
        self.ticket_key = ticket_key
        self.failures = failures
        detail = "; ".join(f"{name}: {msg}" for name, msg in failures.items())
        super().__init__(f"Could not fetch {ticket_key} from any provider ({detail})")


class PipelineError(JiraQACrewError):
    """Base class for pipeline execution failures."""


class StructuredOutputError(PipelineError):
    """An agent did not return output matching the required schema."""


class StageValidationError(PipelineError):
    """Deterministic validation rejected a stage's output."""


class TicketTimeoutError(PipelineError):
    """Processing a single ticket exceeded its time budget."""
