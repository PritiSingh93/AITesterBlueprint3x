"""Provider selection and fallback.

The provider decision is application logic, so these tests pin the exact
behaviour rather than trusting an LLM to choose.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from jira_qa_crew.exceptions import (
    AllProvidersFailedError,
    JiraNotFoundError,
    JiraTransientError,
)
from jira_qa_crew.jira.base import HealthStatus, JiraProvider
from jira_qa_crew.jira.gateway import JiraGateway
from jira_qa_crew.models import JiraIssue, ProviderSource


class StubProvider(JiraProvider):
    def __init__(self, name, *, issue=None, error=None, is_configured=True):
        self.name = name
        self._issue = issue
        self._error = error
        self._configured = is_configured
        self.calls: list[str] = []

    @property
    def configured(self) -> bool:
        return self._configured

    def fetch_issue(self, issue_key: str) -> JiraIssue:
        self.calls.append(issue_key)
        if self._error:
            raise self._error
        return self._issue

    def health_check(self) -> HealthStatus:
        return HealthStatus(self._configured, self.name)


def make_issue(source: ProviderSource) -> JiraIssue:
    return JiraIssue(key="QATEST-7", summary="from " + source.value, source=source)


def build(config, *, mcp=None, rest=None, fixture=None) -> JiraGateway:
    return JiraGateway(
        config,
        mcp_provider=mcp or StubProvider("MCP", error=JiraTransientError("down")),
        rest_provider=rest or StubProvider("REST", error=JiraTransientError("down")),
        fixture_provider=fixture or StubProvider("FIXTURE", is_configured=False),
    )


def test_auto_mode_uses_mcp_when_it_succeeds(base_config) -> None:
    mcp = StubProvider("MCP", issue=make_issue(ProviderSource.MCP))
    rest = StubProvider("REST", issue=make_issue(ProviderSource.REST))
    gateway = build(replace(base_config, jira_integration_mode="auto"), mcp=mcp, rest=rest)

    issue = gateway.fetch_issue("QATEST-7")

    assert issue.source is ProviderSource.MCP
    assert rest.calls == [], "REST must not be called when MCP succeeds"


def test_auto_mode_falls_back_to_rest_when_mcp_fails(base_config) -> None:
    mcp = StubProvider("MCP", error=JiraTransientError("mcp timeout"))
    rest = StubProvider("REST", issue=make_issue(ProviderSource.REST))
    gateway = build(replace(base_config, jira_integration_mode="auto"), mcp=mcp, rest=rest)

    issue = gateway.fetch_issue("QATEST-7")

    assert issue.source is ProviderSource.REST
    assert mcp.calls == ["QATEST-7"], "MCP must be attempted first"


def test_mcp_only_mode_never_touches_rest(base_config) -> None:
    mcp = StubProvider("MCP", error=JiraTransientError("mcp down"))
    rest = StubProvider("REST", issue=make_issue(ProviderSource.REST))
    gateway = build(replace(base_config, jira_integration_mode="mcp"), mcp=mcp, rest=rest)

    with pytest.raises(AllProvidersFailedError):
        gateway.fetch_issue("QATEST-7")
    assert rest.calls == []


def test_rest_only_mode_never_touches_mcp(base_config) -> None:
    mcp = StubProvider("MCP", issue=make_issue(ProviderSource.MCP))
    rest = StubProvider("REST", issue=make_issue(ProviderSource.REST))
    gateway = build(replace(base_config, jira_integration_mode="rest"), mcp=mcp, rest=rest)

    issue = gateway.fetch_issue("QATEST-7")

    assert issue.source is ProviderSource.REST
    assert mcp.calls == []


def test_both_providers_failed_reports_every_reason(base_config) -> None:
    gateway = build(
        replace(base_config, jira_integration_mode="auto"),
        mcp=StubProvider("MCP", error=JiraTransientError("mcp exploded")),
        rest=StubProvider("REST", error=JiraTransientError("rest exploded")),
    )

    with pytest.raises(AllProvidersFailedError) as excinfo:
        gateway.fetch_issue("QATEST-7")

    assert "MCP" in excinfo.value.failures
    assert "REST" in excinfo.value.failures


def test_not_found_stops_immediately_instead_of_trying_rest(base_config) -> None:
    """A missing ticket is authoritative, so the fallback would only confuse."""
    mcp = StubProvider("MCP", error=JiraNotFoundError("QATEST-7 not found"))
    rest = StubProvider("REST", issue=make_issue(ProviderSource.REST))
    gateway = build(replace(base_config, jira_integration_mode="auto"), mcp=mcp, rest=rest)

    with pytest.raises(AllProvidersFailedError):
        gateway.fetch_issue("QATEST-7")
    assert rest.calls == []


def test_failed_live_integration_never_falls_back_to_demo_data(base_config) -> None:
    """The critical safety property: no silent fake-data fallback."""
    fixture = StubProvider("FIXTURE", issue=make_issue(ProviderSource.FIXTURE))
    gateway = build(
        replace(base_config, jira_integration_mode="auto", demo_mode=False),
        mcp=StubProvider("MCP", error=JiraTransientError("down")),
        rest=StubProvider("REST", error=JiraTransientError("down")),
        fixture=fixture,
    )

    with pytest.raises(AllProvidersFailedError):
        gateway.fetch_issue("QATEST-7")
    assert fixture.calls == [], "Demo data must never rescue a failed live run"


def test_demo_mode_uses_fixtures_and_skips_live_providers(base_config) -> None:
    mcp = StubProvider("MCP", issue=make_issue(ProviderSource.MCP))
    fixture = StubProvider("FIXTURE", issue=make_issue(ProviderSource.FIXTURE))
    gateway = build(replace(base_config, demo_mode=True), mcp=mcp, fixture=fixture)

    issue = gateway.fetch_issue("QATEST-7")

    assert issue.source is ProviderSource.FIXTURE
    assert mcp.calls == []


def test_unconfigured_provider_is_skipped_with_a_reason(base_config) -> None:
    mcp = StubProvider("MCP", is_configured=False)
    rest = StubProvider("REST", issue=make_issue(ProviderSource.REST))
    gateway = build(replace(base_config, jira_integration_mode="auto"), mcp=mcp, rest=rest)

    assert gateway.fetch_issue("QATEST-7").source is ProviderSource.REST
    assert mcp.calls == []
