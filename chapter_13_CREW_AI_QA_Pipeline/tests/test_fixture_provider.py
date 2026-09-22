"""Demo-mode fixture provider."""

from __future__ import annotations

import json

import pytest

from jira_qa_crew.exceptions import JiraNotFoundError, JiraProviderUnavailableError
from jira_qa_crew.jira.fixture_provider import JiraFixtureProvider
from jira_qa_crew.models import ProviderSource


def test_available_keys_are_offered_up_front(tmp_path) -> None:
    """A public demo has no Jira to browse, so the UI must name its tickets."""
    (tmp_path / "QATEST-9.json").write_text("{}", encoding="utf-8")
    (tmp_path / "QATEST-7.json").write_text("{}", encoding="utf-8")

    assert JiraFixtureProvider(tmp_path).available_keys() == ["QATEST-7", "QATEST-9"]


def test_available_keys_is_empty_without_a_fixture_directory(tmp_path) -> None:
    assert JiraFixtureProvider(tmp_path / "missing").available_keys() == []


def test_the_shipped_fixtures_are_listable() -> None:
    """The deployed demo depends on these existing, so pin that they do."""
    assert JiraFixtureProvider().available_keys() == ["QATEST-7", "QATEST-9"]


def test_shipped_fixtures_load() -> None:
    provider = JiraFixtureProvider()
    assert provider.configured, "the repo ships fixtures/jira"

    issue = provider.fetch_issue("QATEST-7")

    assert issue.key == "QATEST-7"
    assert "discount" in issue.summary.lower()


def test_fixture_source_is_always_labelled(tmp_path) -> None:
    """Demo output must be visibly demo output, never mistaken for live data."""
    (tmp_path / "AB-1.json").write_text(
        json.dumps({"key": "AB-1", "summary": "x", "source": "REST"}), encoding="utf-8"
    )
    issue = JiraFixtureProvider(tmp_path).fetch_issue("AB-1")
    assert issue.source is ProviderSource.FIXTURE


def test_missing_fixture_lists_what_is_available(tmp_path) -> None:
    (tmp_path / "AB-1.json").write_text(
        json.dumps({"key": "AB-1", "summary": "x"}), encoding="utf-8"
    )
    with pytest.raises(JiraNotFoundError) as excinfo:
        JiraFixtureProvider(tmp_path).fetch_issue("ZZ-9")
    assert "AB-1" in str(excinfo.value)


def test_absent_directory_is_reported(tmp_path) -> None:
    provider = JiraFixtureProvider(tmp_path / "nope")
    assert provider.configured is False
    with pytest.raises(JiraProviderUnavailableError):
        provider.fetch_issue("AB-1")


def test_key_lookup_is_case_insensitive() -> None:
    assert JiraFixtureProvider().fetch_issue("qatest-7").key == "QATEST-7"


def test_injection_fixture_carries_the_attack_text() -> None:
    """The prompt-injection fixture is what the security test exercises."""
    issue = JiraFixtureProvider().fetch_issue("QATEST-9")
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in issue.description
