"""On-screen wording.

The pipeline's enum values are written for machines: they go in manifest.json
and the markdown, where something parses them. A reader should not have to
decode SCREAMING_CASE, so the badges carry a human label and an explanation.
These tests keep the two apart.
"""

from __future__ import annotations

from jira_qa_crew.ui.components import readiness_badge, source_badge
from jira_qa_crew.ui.results import _humanize_duration, _plural


def test_readiness_badge_says_what_it_means() -> None:
    html = readiness_badge("NEEDS_CONFIGURATION")

    assert "Needs setup" in html
    assert "NEEDS_CONFIGURATION" not in html
    assert "selectors or logins" in html  # the hover explanation


def test_source_badge_names_jira_not_just_a_protocol() -> None:
    assert "Jira" in source_badge("REST")
    assert "Demo fixture" in source_badge("FIXTURE")


def test_an_unknown_value_still_renders() -> None:
    """A new enum member must not blank the badge out."""
    assert "SOMETHING_NEW" in readiness_badge("SOMETHING_NEW")


def test_badge_text_is_escaped() -> None:
    assert "<script>" not in source_badge("<script>")


def test_durations_are_written_the_way_people_say_them() -> None:
    assert _humanize_duration(105.52) == "1m 46s"
    assert _humanize_duration(41) == "41s"
    assert _humanize_duration(3600) == "60m 00s"
    assert _humanize_duration(None) == "—"
    assert _humanize_duration(0) == "—"


def test_counts_read_as_sentences() -> None:
    assert _plural(1, "ticket") == "1 ticket"
    assert _plural(0, "ticket") == "0 tickets"
    assert _plural(6, "detail") == "6 details"
