"""Jira provider abstraction."""

from __future__ import annotations

import abc
from dataclasses import dataclass

from ..models import JiraIssue


@dataclass
class HealthStatus:
    healthy: bool
    detail: str


class JiraProvider(abc.ABC):
    """Read-only access to a single Jira issue."""

    name: str = "provider"

    @property
    @abc.abstractmethod
    def configured(self) -> bool:
        """Whether this provider has enough configuration to be attempted."""

    @abc.abstractmethod
    def fetch_issue(self, issue_key: str) -> JiraIssue:
        """Fetch one issue, or raise a :class:`~..exceptions.JiraError`."""

    def health_check(self) -> HealthStatus:
        if not self.configured:
            return HealthStatus(False, f"{self.name} is not configured")
        return HealthStatus(True, f"{self.name} configuration present")
