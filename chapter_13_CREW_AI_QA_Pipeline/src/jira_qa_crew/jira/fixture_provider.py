"""Local fixture provider used only when DEMO_MODE is explicitly enabled.

This provider is never selected as an automatic fallback for a failed live
integration. :class:`~.gateway.JiraGateway` only uses it when demo mode is on,
and every artifact it produces is labelled ``FIXTURE``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..exceptions import JiraNotFoundError, JiraProviderUnavailableError
from ..logging_utils import get_logger
from ..models import JiraIssue, ProviderSource
from .base import HealthStatus, JiraProvider

logger = get_logger("jira.fixture")

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "jira"


class JiraFixtureProvider(JiraProvider):
    name = "FIXTURE"

    def __init__(self, fixture_dir: Path | str | None = None) -> None:
        self._dir = Path(fixture_dir) if fixture_dir else DEFAULT_FIXTURE_DIR

    @property
    def configured(self) -> bool:
        return self._dir.is_dir()

    def fetch_issue(self, issue_key: str) -> JiraIssue:
        if not self.configured:
            raise JiraProviderUnavailableError(
                f"Demo mode is on but no fixture directory exists at {self._dir}."
            )
        path = self._dir / f"{issue_key.upper()}.json"
        if not path.is_file():
            available = ", ".join(sorted(p.stem for p in self._dir.glob("*.json")))
            raise JiraNotFoundError(
                f"No demo fixture for {issue_key}. Available: {available or 'none'}"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        data["source"] = ProviderSource.FIXTURE.value
        issue = JiraIssue.model_validate(data)
        logger.info("Loaded %s from demo fixture", issue_key)
        return issue

    def health_check(self) -> HealthStatus:
        if not self.configured:
            return HealthStatus(False, f"No fixture directory at {self._dir}")
        count = len(list(self._dir.glob("*.json")))
        return HealthStatus(True, f"{count} demo fixtures available")
