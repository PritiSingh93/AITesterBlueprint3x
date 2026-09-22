"""Coverage and traceability computation."""

from __future__ import annotations

from jira_qa_crew.models import CoverageStatus, PlaywrightBundle, TestCaseSuite
from jira_qa_crew.services.traceability import automatable_cases, build_coverage


def test_full_coverage_is_detected(analysis, suite, bundle) -> None:
    report = build_coverage(analysis, suite, bundle)

    assert report.total_requirements == 2
    assert report.covered_requirements == 2
    assert report.total_acceptance_criteria == 2
    assert report.covered_acceptance_criteria == 2
    assert report.requirement_coverage_pct == 100.0
    assert report.orphan_requirements == []


def test_requirement_with_no_test_case_is_an_orphan(analysis, bundle) -> None:
    report = build_coverage(analysis, TestCaseSuite(), bundle)

    assert set(report.orphan_requirements) == {"REQ-001", "REQ-002"}
    assert report.covered_requirements == 0
    assert report.requirement_coverage_pct == 0.0


def test_test_case_tracing_to_nothing_is_an_orphan(analysis, suite, bundle) -> None:
    suite.test_cases[0].requirement_ids = []
    suite.test_cases[0].acceptance_criteria_ids = []

    report = build_coverage(analysis, suite, bundle)

    assert suite.test_cases[0].id in report.orphan_test_cases


def test_criteria_sharing_a_requirement_do_not_collect_every_case(
    analysis, suite, bundle
) -> None:
    """The real shape of an analysis: several criteria under the same requirements.

    A case that names its own criterion must land on that criterion's row only.
    Falling back to the parent requirement for it as well put all four cases on
    both rows and the matrix claimed everything covered everything.
    """
    for criterion in analysis.analysis.acceptance_criteria:
        criterion.requirement_ids = ["REQ-001", "REQ-002"]
    for case in suite.test_cases:
        case.requirement_ids = ["REQ-001", "REQ-002"]

    report = build_coverage(analysis, suite, bundle)
    by_ac = {row.acceptance_criterion_id: row.test_case_ids for row in report.rows}

    assert by_ac["AC-001"] == ["QATEST-7-TC-001", "QATEST-7-TC-002"]
    assert by_ac["AC-002"] == ["QATEST-7-TC-003", "QATEST-7-TC-004"]


def test_a_case_naming_no_criterion_falls_back_to_its_requirement(
    analysis, suite, bundle
) -> None:
    """The fallback still applies where there is nothing more precise to use."""
    suite.test_cases[0].acceptance_criteria_ids = []
    suite.test_cases[0].requirement_ids = ["REQ-002"]

    report = build_coverage(analysis, suite, bundle)
    by_ac = {row.acceptance_criterion_id: row.test_case_ids for row in report.rows}

    assert "QATEST-7-TC-001" in by_ac["AC-002"]
    assert "QATEST-7-TC-001" not in by_ac["AC-001"]


def test_unknown_reference_is_reported(analysis, suite, bundle) -> None:
    suite.test_cases[0].requirement_ids = ["REQ-404"]

    report = build_coverage(analysis, suite, bundle)

    assert "REQ-404" in report.unknown_requirement_refs


def test_positive_only_coverage_is_partial(analysis, suite, bundle) -> None:
    """A criterion with no negative or boundary case is only partly covered."""
    for case in suite.test_cases:
        case.test_type = "Functional"
        case.title = "Happy path"
        case.tags = []

    report = build_coverage(analysis, suite, bundle)
    statuses = {row.coverage_status for row in report.rows if row.test_case_ids}

    assert CoverageStatus.PARTIAL in statuses


def test_automated_cases_are_counted_from_the_bundle(analysis, suite, bundle) -> None:
    report = build_coverage(analysis, suite, bundle)
    assert report.automated_test_cases == 1
    assert report.total_test_cases == 4


def test_coverage_without_a_bundle_reports_manual_only(analysis, suite) -> None:
    report = build_coverage(analysis, suite, None)
    assert report.automated_test_cases == 0
    assert all(not row.automated_test_case_ids for row in report.rows)


def test_empty_bundle_mappings_mean_no_automation(analysis, suite) -> None:
    report = build_coverage(analysis, suite, PlaywrightBundle())
    assert report.automated_test_cases == 0


def test_automatable_cases_include_yes_and_partial(suite) -> None:
    ids = automatable_cases(suite)
    assert len(ids) == 4  # three Yes plus one Partial in the fixture


def test_coverage_percentages_handle_zero_requirements(analysis, suite, bundle) -> None:
    analysis.analysis.functional_requirements = []
    analysis.analysis.non_functional_requirements = []
    analysis.analysis.acceptance_criteria = []

    report = build_coverage(analysis, suite, bundle)

    assert report.requirement_coverage_pct == 0.0
    assert report.acceptance_criteria_coverage_pct == 0.0
