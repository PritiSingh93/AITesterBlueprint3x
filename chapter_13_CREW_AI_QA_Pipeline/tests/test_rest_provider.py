"""Jira REST provider: parsing and the HTTP error taxonomy."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
import requests

from jira_qa_crew.exceptions import (
    JiraAuthError,
    JiraNotFoundError,
    JiraPermissionError,
    JiraProviderUnavailableError,
    JiraTransientError,
)
from jira_qa_crew.jira.rest_provider import JiraRestProvider
from jira_qa_crew.models import ProviderSource

ISSUE_JSON = {
    "key": "QATEST-7",
    "fields": {
        "summary": "Cart total shows $0.00",
        "description": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Totals render as zero."}],
                }
            ],
        },
        "issuetype": {"name": "Bug"},
        "status": {"name": "Open"},
        "priority": {"name": "High"},
        "labels": ["checkout"],
        "components": [{"name": "Cart"}],
        "parent": {"key": "QATEST-1"},
        "subtasks": [{"key": "QATEST-8"}],
        "issuelinks": [{"outwardIssue": {"key": "QATEST-3"}}],
        "customfield_101": "AC: totals must match the API.",
        "comment": {
            "comments": [
                {"author": {"displayName": "Jane"}, "body": "Reproduced on Chrome."}
            ]
        },
    },
}


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        item = self._responses.pop(0) if self._responses else self._responses
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def rest_config(base_config):
    return replace(base_config.rest, acceptance_criteria_field="customfield_101",
                   include_comments=True)


def test_parses_every_field_including_adf(rest_config) -> None:
    provider = JiraRestProvider(
        rest_config, session=FakeSession([FakeResponse(200, ISSUE_JSON)])
    )
    issue = provider.fetch_issue("QATEST-7")

    assert issue.key == "QATEST-7"
    assert issue.issue_type == "Bug"
    assert issue.priority == "High"
    assert "Totals render as zero." in issue.description
    assert issue.labels == ["checkout"]
    assert issue.components == ["Cart"]
    assert issue.parent == "QATEST-1"
    assert issue.subtasks == ["QATEST-8"]
    assert issue.linked_issues == ["QATEST-3"]
    assert "totals must match" in issue.acceptance_criteria_raw
    assert issue.comments and "Jane" in issue.comments[0]
    assert issue.source is ProviderSource.REST


def test_comments_are_excluded_unless_enabled(base_config) -> None:
    config = replace(base_config.rest, include_comments=False)
    provider = JiraRestProvider(
        config, session=FakeSession([FakeResponse(200, ISSUE_JSON)])
    )
    assert provider.fetch_issue("QATEST-7").comments == []


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, JiraAuthError),
        (403, JiraPermissionError),
        (404, JiraNotFoundError),
    ],
)
def test_http_errors_map_to_typed_exceptions(rest_config, status, expected) -> None:
    provider = JiraRestProvider(
        rest_config, session=FakeSession([FakeResponse(status, {})]), max_retries=0
    )
    with pytest.raises(expected):
        provider.fetch_issue("QATEST-7")


def test_server_errors_are_retried_then_raised(rest_config) -> None:
    session = FakeSession([FakeResponse(503, {}), FakeResponse(503, {})])
    provider = JiraRestProvider(
        rest_config, session=session, max_retries=1, backoff_base=0
    )
    with pytest.raises(JiraTransientError):
        provider.fetch_issue("QATEST-7")
    assert session.calls == 2, "one retry means two attempts"


def test_transient_failure_then_success_recovers(rest_config) -> None:
    session = FakeSession([FakeResponse(503, {}), FakeResponse(200, ISSUE_JSON)])
    provider = JiraRestProvider(
        rest_config, session=session, max_retries=1, backoff_base=0
    )
    assert provider.fetch_issue("QATEST-7").key == "QATEST-7"


def test_timeout_becomes_a_transient_error(rest_config) -> None:
    provider = JiraRestProvider(
        rest_config,
        session=FakeSession([requests.Timeout("slow")]),
        max_retries=0,
    )
    with pytest.raises(JiraTransientError):
        provider.fetch_issue("QATEST-7")


def test_unconfigured_provider_refuses_to_call(base_config) -> None:
    config = replace(base_config.rest, url="", email="", api_token="")
    provider = JiraRestProvider(config)
    assert provider.configured is False
    with pytest.raises(JiraProviderUnavailableError):
        provider.fetch_issue("QATEST-7")
