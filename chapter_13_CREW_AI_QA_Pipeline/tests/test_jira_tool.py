"""The read-only Jira tool exposed to the analyst agent."""

from __future__ import annotations

from jira_qa_crew.exceptions import JiraNotFoundError
from jira_qa_crew.models import JiraIssue, ProviderSource
from jira_qa_crew.security import UNTRUSTED_CLOSE, UNTRUSTED_OPEN
from jira_qa_crew.tools.jira_tool import FetchJiraIssueInput, FetchJiraIssueTool


class StubGateway:
    def __init__(self, issue=None, error=None):
        self._issue = issue
        self._error = error
        self.calls: list[str] = []

    def fetch_issue(self, issue_key: str):
        self.calls.append(issue_key)
        if self._error:
            raise self._error
        return self._issue


def test_schema_exposes_only_issue_key() -> None:
    """A wide schema is what strict providers reject with a 400."""
    assert list(FetchJiraIssueInput.model_fields) == ["issue_key"]


def test_primed_issue_is_served_without_a_network_call(issue: JiraIssue) -> None:
    gateway = StubGateway()
    tool = FetchJiraIssueTool(gateway=gateway)
    tool.prime(issue)

    result = tool._run(issue_key="QATEST-7")

    assert "Cart total" in result
    assert gateway.calls == [], "a primed issue must not be refetched"


def test_output_is_fenced_as_untrusted(issue: JiraIssue) -> None:
    tool = FetchJiraIssueTool()
    tool.prime(issue)

    result = tool._run(issue_key="QATEST-7")

    assert UNTRUSTED_OPEN in result
    assert UNTRUSTED_CLOSE in result


def test_lower_case_key_still_resolves(issue: JiraIssue) -> None:
    tool = FetchJiraIssueTool()
    tool.prime(issue)
    assert "Cart total" in tool._run(issue_key="qatest-7")


def test_out_of_scope_ticket_is_refused(issue: JiraIssue) -> None:
    """Prompt injection must not widen data access to other tickets."""
    gateway = StubGateway(issue=issue)
    tool = FetchJiraIssueTool(gateway=gateway)
    tool.prime(issue)

    result = tool._run(issue_key="ADMIN-1")

    assert "Refused" in result
    assert gateway.calls == [], "the gateway must never be reached for a refused key"


def test_refusal_tells_the_agent_to_record_it(issue: JiraIssue) -> None:
    tool = FetchJiraIssueTool()
    tool.prime(issue)
    assert "open_questions" in tool._run(issue_key="ADMIN-1")


def test_missing_key_is_handled() -> None:
    assert "Error" in FetchJiraIssueTool()._run(issue_key="")


def test_gateway_error_is_returned_as_text_not_raised() -> None:
    """A tool exception would abort the crew; a message lets it recover."""
    tool = FetchJiraIssueTool(gateway=StubGateway(error=JiraNotFoundError("gone")))
    tool.allowed_keys.add("QATEST-7")

    result = tool._run(issue_key="QATEST-7")

    assert "Error reading QATEST-7" in result


def test_no_gateway_and_no_cache_reports_clearly() -> None:
    tool = FetchJiraIssueTool()
    tool.allowed_keys.add("QATEST-7")
    assert "no Jira gateway" in tool._run(issue_key="QATEST-7")


def test_tool_declares_itself_read_only() -> None:
    assert "read-only" in FetchJiraIssueTool().description.lower()


def test_priming_records_the_source(issue: JiraIssue) -> None:
    issue.source = ProviderSource.MCP
    tool = FetchJiraIssueTool()
    tool.prime(issue)
    assert tool.cache["QATEST-7"].source is ProviderSource.MCP
