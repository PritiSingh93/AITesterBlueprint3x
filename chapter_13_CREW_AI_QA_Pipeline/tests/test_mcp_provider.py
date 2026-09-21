"""MCP provider: tool resolution, read-only enforcement and response parsing.

No MCP server is started. These cover the logic that runs around the transport.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from jira_qa_crew.config import JiraMCPConfig
from jira_qa_crew.exceptions import (
    JiraNotFoundError,
    JiraProviderUnavailableError,
    JiraResponseError,
)
from jira_qa_crew.jira.mcp_provider import JiraMCPProvider, _is_read_only
from jira_qa_crew.models import ProviderSource


@pytest.fixture
def mcp_config() -> JiraMCPConfig:
    return JiraMCPConfig(
        transport="stdio",
        url="",
        command="uvx",
        args=["mcp-atlassian"],
        headers={},
        env={},
        get_issue_tool="",
        issue_key_argument="issue_key",
        timeout_seconds=20,
        allowed_tools=frozenset({"jira_get_issue", "get_issue"}),
    )


@pytest.fixture
def provider(mcp_config) -> JiraMCPProvider:
    return JiraMCPProvider(mcp_config)


# -- read-only enforcement --------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "jira_create_issue",
        "jira_update_issue",
        "jira_delete_issue",
        "jira_transition_issue",
        "jira_add_comment",
        "jira_batch_create",
    ],
)
def test_mutating_tool_names_are_rejected(name: str) -> None:
    assert _is_read_only(name) is False


@pytest.mark.parametrize("name", ["jira_get_issue", "get_issue", "jira_search"])
def test_read_only_tool_names_are_accepted(name: str) -> None:
    assert _is_read_only(name) is True


def test_a_mutating_tool_is_never_chosen_even_if_allowlisted(mcp_config) -> None:
    config = replace(mcp_config, allowed_tools=frozenset({"jira_delete_issue"}))
    provider = JiraMCPProvider(config)

    with pytest.raises(JiraResponseError):
        provider._resolve_tool_name(["jira_delete_issue"])


# -- tool resolution --------------------------------------------------------


def test_configured_tool_name_wins(mcp_config) -> None:
    config = replace(mcp_config, get_issue_tool="customGetIssue")
    provider = JiraMCPProvider(config)

    assert provider._resolve_tool_name(["customGetIssue", "other"]) == "customGetIssue"


def test_configured_tool_missing_is_an_explicit_error(mcp_config) -> None:
    config = replace(mcp_config, get_issue_tool="notThere")
    provider = JiraMCPProvider(config)

    with pytest.raises(JiraResponseError) as excinfo:
        provider._resolve_tool_name(["jira_get_issue"])
    assert "does not expose" in str(excinfo.value)


def test_allowlisted_tool_is_detected(provider) -> None:
    assert provider._resolve_tool_name(["jira_get_issue", "jira_search"]) == (
        "jira_get_issue"
    )


def test_unconventional_name_is_discovered_by_hint(provider) -> None:
    """Server naming differs, so the tool name is never assumed."""
    assert provider._resolve_tool_name(["atlassian_read_issue"]) == (
        "atlassian_read_issue"
    )


def test_no_usable_tool_gives_actionable_guidance(provider) -> None:
    with pytest.raises(JiraResponseError) as excinfo:
        provider._resolve_tool_name(["unrelated_tool"])
    assert "JIRA_MCP_GET_ISSUE_TOOL" in str(excinfo.value)


# -- configuration ----------------------------------------------------------


def test_stdio_needs_a_command(mcp_config) -> None:
    assert JiraMCPProvider(replace(mcp_config, command="")).configured is False


def test_http_transport_needs_a_url(mcp_config) -> None:
    config = replace(mcp_config, transport="streamable_http", command="", url="")
    assert JiraMCPProvider(config).configured is False
    assert JiraMCPProvider(replace(config, url="https://mcp.example")).configured


def test_unconfigured_provider_refuses_to_fetch(mcp_config) -> None:
    provider = JiraMCPProvider(replace(mcp_config, command=""))
    with pytest.raises(JiraProviderUnavailableError):
        provider.fetch_issue("QATEST-7")


# -- response parsing -------------------------------------------------------


def test_flat_json_response_is_parsed(provider) -> None:
    raw = json.dumps(
        {
            "key": "QATEST-7",
            "summary": "Cart total is zero",
            "description": "Totals render as zero.",
            "status": {"name": "Open"},
            "priority": {"name": "High"},
            "labels": ["checkout"],
            "components": [{"name": "Cart"}],
        }
    )
    issue = provider._parse("QATEST-7", raw)

    assert issue.key == "QATEST-7"
    assert issue.status == "Open"
    assert issue.priority == "High"
    assert issue.components == ["Cart"]
    assert issue.source is ProviderSource.MCP


def test_nested_fields_response_is_parsed(provider) -> None:
    raw = json.dumps(
        {
            "key": "QATEST-7",
            "fields": {
                "summary": "Nested summary",
                "issuetype": {"name": "Bug"},
                "status": {"name": "Open"},
            },
        }
    )
    issue = provider._parse("QATEST-7", raw)

    assert issue.summary == "Nested summary"
    assert issue.issue_type == "Bug"


def test_adf_description_from_mcp_is_flattened(provider) -> None:
    raw = json.dumps(
        {
            "key": "QATEST-7",
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "ADF body"}],
                    }
                ],
            },
        }
    )
    assert "ADF body" in provider._parse("QATEST-7", raw).description


def test_prose_response_is_kept_rather_than_discarded(provider) -> None:
    issue = provider._parse("QATEST-7", "The cart total renders as zero.")
    assert "renders as zero" in issue.description
    assert issue.key == "QATEST-7"


def test_not_found_message_raises(provider) -> None:
    raw = json.dumps({"error": "Issue does not exist or you lack permission"})
    with pytest.raises(JiraNotFoundError):
        provider._parse("QATEST-7", raw)


def test_empty_payload_raises(provider) -> None:
    with pytest.raises(JiraResponseError):
        provider._parse("QATEST-7", "   ")


def test_list_response_is_unwrapped(provider) -> None:
    raw = json.dumps([{"key": "QATEST-7", "summary": "From a list"}])
    assert provider._parse("QATEST-7", raw).summary == "From a list"


def test_issue_links_are_flattened_to_keys(provider) -> None:
    raw = json.dumps(
        {
            "key": "QATEST-7",
            "issuelinks": [{"outwardIssue": {"key": "QATEST-3"}}],
        }
    )
    assert provider._parse("QATEST-7", raw).linked_issues == ["QATEST-3"]
