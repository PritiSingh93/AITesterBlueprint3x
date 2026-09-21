"""Jira Cloud REST API provider (fallback path)."""

from __future__ import annotations

import time
from typing import Any

import requests

from ..config import JiraRestConfig
from ..exceptions import (
    JiraAuthError,
    JiraNotFoundError,
    JiraPermissionError,
    JiraProviderUnavailableError,
    JiraRateLimitError,
    JiraResponseError,
    JiraTransientError,
)
from ..logging_utils import get_logger, redact
from ..models import JiraIssue, ProviderSource
from .adf import extract_text
from .base import HealthStatus, JiraProvider

logger = get_logger("jira.rest")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class JiraRestProvider(JiraProvider):
    name = "REST"

    def __init__(
        self,
        config: JiraRestConfig,
        *,
        session: requests.Session | None = None,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    @property
    def configured(self) -> bool:
        return self._config.configured

    # -- request plumbing --------------------------------------------------

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._config.auth_mode == "bearer" and self._config.bearer_token:
            headers["Authorization"] = f"Bearer {self._config.bearer_token}"
        return headers

    def _auth(self) -> tuple[str, str] | None:
        if self._config.auth_mode == "bearer":
            return None
        return (self._config.email, self._config.api_token)

    def _raise_for_status(self, response: requests.Response, issue_key: str) -> None:
        status = response.status_code
        if status < 400:
            return
        if status == 401:
            raise JiraAuthError(
                "Jira rejected the credentials (401). Check JIRA_EMAIL and "
                "JIRA_API_TOKEN, or JIRA_BEARER_TOKEN for bearer auth."
            )
        if status == 403:
            raise JiraPermissionError(
                f"Not permitted to read {issue_key} (403). The account lacks "
                "Browse Projects permission on that project."
            )
        if status == 404:
            raise JiraNotFoundError(
                f"{issue_key} was not found (404). Check the key and that the "
                "account can see the project."
            )
        if status == 429:
            raise JiraRateLimitError(
                f"Jira rate limited the request for {issue_key} (429)."
            )
        if status in _RETRYABLE_STATUS:
            raise JiraTransientError(f"Jira returned {status} for {issue_key}.")
        raise JiraResponseError(
            f"Jira returned {status} for {issue_key}: {redact(response.text[:300])}"
        )

    def _get(self, url: str, params: dict[str, str], issue_key: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    auth=self._auth(),
                    headers=self._auth_headers(),
                    timeout=self._config.timeout_seconds,
                )
                self._raise_for_status(response, issue_key)
                return response.json()
            except (JiraTransientError, JiraRateLimitError) as exc:
                last_error = exc
            except requests.Timeout as exc:
                last_error = JiraTransientError(
                    f"Jira request for {issue_key} timed out after "
                    f"{self._config.timeout_seconds}s."
                )
                last_error.__cause__ = exc
            except requests.RequestException as exc:
                last_error = JiraTransientError(
                    f"Could not reach Jira for {issue_key}: {redact(exc)}"
                )
            except ValueError as exc:
                raise JiraResponseError(
                    f"Jira returned a non-JSON body for {issue_key}."
                ) from exc

            if attempt < self._max_retries:
                delay = self._backoff_base * (2**attempt)
                logger.warning(
                    "REST attempt %s/%s for %s failed, retrying in %.1fs",
                    attempt + 1,
                    self._max_retries + 1,
                    issue_key,
                    delay,
                )
                time.sleep(delay)

        assert last_error is not None
        raise last_error

    # -- public API --------------------------------------------------------

    def fetch_issue(self, issue_key: str) -> JiraIssue:
        if not self.configured:
            raise JiraProviderUnavailableError(
                "Jira REST is not configured (need JIRA_URL and credentials)."
            )
        base = self._config.url.rstrip("/")
        url = f"{base}/rest/api/{self._config.api_version}/issue/{issue_key}"
        params = {"expand": "names"}
        payload = self._get(url, params, issue_key)
        issue = self._to_issue(issue_key, payload, base)
        logger.info("Fetched %s via REST", issue_key)
        return issue

    def health_check(self) -> HealthStatus:
        if not self.configured:
            return HealthStatus(False, "REST not configured")
        base = self._config.url.rstrip("/")
        try:
            response = self._session.get(
                f"{base}/rest/api/{self._config.api_version}/myself",
                auth=self._auth(),
                headers=self._auth_headers(),
                timeout=self._config.timeout_seconds,
            )
            if response.status_code == 200:
                return HealthStatus(True, "REST reachable")
            return HealthStatus(False, f"REST returned {response.status_code}")
        except requests.RequestException as exc:
            return HealthStatus(False, f"REST unreachable: {redact(exc)}")

    # -- parsing -----------------------------------------------------------

    def _to_issue(self, issue_key: str, payload: dict[str, Any], base: str) -> JiraIssue:
        fields = payload.get("fields")
        if not isinstance(fields, dict):
            raise JiraResponseError(
                f"Jira response for {issue_key} has no 'fields' object."
            )

        ac_field = self._config.acceptance_criteria_field
        acceptance = extract_text(fields.get(ac_field)) if ac_field else ""

        comments: list[str] = []
        if self._config.include_comments:
            container = fields.get("comment") or {}
            for entry in (container.get("comments") or [])[: self._config.max_comments]:
                author = ((entry.get("author") or {}).get("displayName")) or "Unknown"
                body = extract_text(entry.get("body"))
                if body:
                    comments.append(f"{author}: {body}")

        return JiraIssue(
            key=payload.get("key") or issue_key,
            summary=str(fields.get("summary") or ""),
            description=extract_text(fields.get("description")),
            issue_type=str((fields.get("issuetype") or {}).get("name") or "Unknown"),
            status=str((fields.get("status") or {}).get("name") or "Unknown"),
            priority=str((fields.get("priority") or {}).get("name") or "Not set"),
            labels=[str(x) for x in (fields.get("labels") or [])],
            components=[
                str(c.get("name")) for c in (fields.get("components") or []) if c
            ],
            parent=((fields.get("parent") or {}).get("key")),
            subtasks=[str(s.get("key")) for s in (fields.get("subtasks") or []) if s],
            linked_issues=_linked_keys(fields.get("issuelinks") or []),
            acceptance_criteria_raw=acceptance,
            comments=comments,
            url=f"{base}/browse/{payload.get('key') or issue_key}",
            source=ProviderSource.REST,
        )


def _linked_keys(links: list[dict[str, Any]]) -> list[str]:
    keys: list[str] = []
    for link in links:
        for side in ("inwardIssue", "outwardIssue"):
            issue = link.get(side)
            if isinstance(issue, dict) and issue.get("key"):
                keys.append(str(issue["key"]))
    return keys
