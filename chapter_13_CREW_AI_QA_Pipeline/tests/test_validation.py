"""Deterministic stage validation."""

from __future__ import annotations

import pytest

from jira_qa_crew.models import (
    AnalysisPayload,
    AutomationReadiness,
    InfoClass,
    PlaywrightBundle,
    PlaywrightFile,
    Requirement,
    TestCaseSuite,
    TestPlanSection,
)
from jira_qa_crew.services import validation


def codes(issues) -> set[str]:
    return {i.code for i in issues}


# -- analysis ---------------------------------------------------------------


def test_clean_analysis_produces_no_issues(payload) -> None:
    assert validation.validate_analysis(payload) == []


def test_duplicate_requirement_ids_are_errors(payload) -> None:
    payload.functional_requirements.append(
        Requirement(id="REQ-001", text="duplicate", evidence="x")
    )
    issues = validation.validate_analysis(payload)
    assert "duplicate_requirement_id" in codes(issues)
    assert validation.has_errors(issues)


def test_empty_analysis_is_an_error() -> None:
    issues = validation.validate_analysis(AnalysisPayload())
    assert "no_requirements" in codes(issues)


def test_explicit_requirement_without_evidence_warns(payload) -> None:
    payload.functional_requirements[0].evidence = ""
    assert "missing_evidence" in codes(validation.validate_analysis(payload))


def test_acceptance_criterion_pointing_at_unknown_requirement_warns(payload) -> None:
    payload.acceptance_criteria[0].requirement_ids = ["REQ-999"]
    assert "unknown_requirement_ref" in codes(validation.validate_analysis(payload))


# -- test plan --------------------------------------------------------------


def test_complete_plan_passes(plan, analysis) -> None:
    assert validation.validate_test_plan(plan, analysis) == []


def test_missing_sections_are_reported(plan, analysis) -> None:
    plan.sections = plan.sections[:10]
    issues = validation.validate_test_plan(plan, analysis)
    assert "section_count" in codes(issues)
    assert "missing_sections" in codes(issues)


def test_empty_section_is_an_error(plan, analysis) -> None:
    plan.sections[3] = TestPlanSection(number=4, title="Out of Scope", content="   ")
    issues = validation.validate_test_plan(plan, analysis)
    assert "empty_section" in codes(issues)
    assert validation.has_errors(issues)


def test_scenario_with_no_traceability_warns(plan, analysis) -> None:
    plan.scenarios[0].requirement_ids = []
    plan.scenarios[0].acceptance_criteria_ids = []
    assert "untraceable_scenario" in codes(validation.validate_test_plan(plan, analysis))


def test_scenario_referencing_unknown_id_warns(plan, analysis) -> None:
    plan.scenarios[0].requirement_ids = ["REQ-404"]
    assert "unknown_scenario_ref" in codes(validation.validate_test_plan(plan, analysis))


# -- test cases -------------------------------------------------------------


def test_clean_suite_passes(suite, analysis) -> None:
    assert validation.validate_test_cases(suite, analysis) == []


def test_duplicate_test_case_ids_are_errors(suite, analysis) -> None:
    suite.test_cases[1].id = suite.test_cases[0].id
    issues = validation.validate_test_cases(suite, analysis)
    assert "duplicate_test_case_id" in codes(issues)
    assert validation.has_errors(issues)


def test_case_without_steps_is_an_error(suite, analysis) -> None:
    suite.test_cases[0].steps = []
    assert "no_steps" in codes(validation.validate_test_cases(suite, analysis))


def test_uncovered_explicit_acceptance_criterion_warns(suite, analysis) -> None:
    for case in suite.test_cases:
        case.acceptance_criteria_ids = [
            ac for ac in case.acceptance_criteria_ids if ac != "AC-002"
        ]
    assert "uncovered_acceptance_criterion" in codes(
        validation.validate_test_cases(suite, analysis)
    )


def test_inferred_criterion_without_a_case_does_not_warn(suite, analysis) -> None:
    analysis.analysis.acceptance_criteria[1].classification = InfoClass.INFERRED
    for case in suite.test_cases:
        case.acceptance_criteria_ids = [
            ac for ac in case.acceptance_criteria_ids if ac != "AC-002"
        ]
    assert "uncovered_acceptance_criterion" not in codes(
        validation.validate_test_cases(suite, analysis)
    )


def test_empty_suite_is_an_error(analysis) -> None:
    issues = validation.validate_test_cases(TestCaseSuite(), analysis)
    assert "no_test_cases" in codes(issues)


# -- playwright -------------------------------------------------------------


def test_clean_bundle_passes(bundle, suite) -> None:
    assert validation.validate_playwright(bundle, suite) == []


def test_hard_wait_is_rejected(bundle, suite) -> None:
    bundle.files[0].content += "\nawait page.waitForTimeout(3000);\n"
    issues = validation.validate_playwright(bundle, suite)
    assert "banned_pattern" in codes(issues)
    assert validation.has_errors(issues)


def test_hard_coded_credential_is_rejected(bundle, suite) -> None:
    bundle.files[0].content += "\nconst password = 'hunter2secret';\n"
    assert "banned_pattern" in codes(validation.validate_playwright(bundle, suite))


@pytest.mark.parametrize(
    "line",
    [
        # Taken from a real run: the agent used marked placeholders rather than
        # inventing credentials, which is exactly what it is told to do.
        "const A = { username: '<<USER_A_USERNAME>>', password: '<<USER_A_PASSWORD>>' };",
        "const token = process.env.AUTH_TOKEN ?? '<<AUTH_TOKEN>>';",
        "const password = 'CHANGE_ME';",
        "const apiKey = 'YOUR_API_KEY_HERE';",
        "const secret = '{{VAULT_SECRET}}';",
        "const password = process.env.TEST_PASSWORD;",
        "const token = `Bearer ${process.env.AUTH_TOKEN}`;",
    ],
)
def test_placeholder_credentials_are_not_flagged(bundle, suite, line: str) -> None:
    """Penalising a placeholder would punish the agent for being honest."""
    bundle.files[0].content += f"\n{line}\n"
    assert "banned_pattern" not in codes(validation.validate_playwright(bundle, suite))


def test_credential_message_does_not_echo_the_secret(bundle, suite) -> None:
    bundle.files[0].content += "\nconst password = 'hunter2secretvalue';\n"
    messages = " ".join(
        i.message for i in validation.validate_playwright(bundle, suite)
    )
    assert "hunter2secretvalue" not in messages


def test_hard_coded_environment_url_is_rejected(bundle, suite) -> None:
    bundle.files[0].content += "\nawait page.goto('https://staging.acme.internal/cart');\n"
    assert "banned_pattern" in codes(validation.validate_playwright(bundle, suite))


def test_localhost_url_is_allowed(bundle, suite) -> None:
    bundle.files[0].content += "\nawait page.goto('http://localhost:3000/cart');\n"
    assert "banned_pattern" not in codes(validation.validate_playwright(bundle, suite))


def test_ready_claim_with_placeholders_is_flagged(bundle, suite) -> None:
    bundle.readiness = AutomationReadiness.READY
    bundle.files[0].content += "\nconst CART_URL = 'TODO';\n"
    assert "readiness_overclaim" in codes(validation.validate_playwright(bundle, suite))


def test_no_files_despite_automatable_cases_is_an_error(suite) -> None:
    empty = PlaywrightBundle(files=[], mappings=[])
    issues = validation.validate_playwright(empty, suite)
    assert "no_files" in codes(issues)
    assert validation.has_errors(issues)


def test_mapping_to_unknown_test_case_warns(bundle, suite) -> None:
    bundle.mappings[0].test_case_id = "QATEST-7-TC-999"
    assert "unknown_mapping" in codes(validation.validate_playwright(bundle, suite))


def test_empty_generated_file_is_an_error(bundle, suite) -> None:
    bundle.files.append(PlaywrightFile(path="tests/blank.spec.ts", content="  "))
    assert "empty_file" in codes(validation.validate_playwright(bundle, suite))
