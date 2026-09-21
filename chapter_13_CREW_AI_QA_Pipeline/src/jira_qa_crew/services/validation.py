"""Deterministic validation applied after every stage.

These checks are Python, not prompt instructions, so a confident-sounding but
malformed model response still fails loudly.
"""

from __future__ import annotations

import re

from ..models import (
    TEST_PLAN_SECTIONS,
    AnalysisPayload,
    AutomationCandidate,
    AutomationReadiness,
    CoverageReport,
    InfoClass,
    PlaywrightBundle,
    RequirementAnalysis,
    Severity,
    TestCaseSuite,
    TestPlan,
    ValidationIssue,
)

# Patterns that make a generated suite flaky or unsafe.
_BANNED_CODE = (
    (re.compile(r"waitForTimeout\s*\("), "uses page.waitForTimeout (hard wait)"),
    (re.compile(r"\bsleep\s*\(", re.IGNORECASE), "uses a sleep call"),
    (
        re.compile(r"""['"]https?://(?!localhost|127\.0\.0\.1|example\.(com|org))[^'"]+['"]"""),
        "hard-codes an absolute environment URL instead of using baseURL",
    ),
)

_CREDENTIAL_ASSIGNMENT = re.compile(
    r"""(?:password|passwd|secret|api[_-]?key|auth[_-]?token|\btoken)\s*[:=]\s*"""
    r"""(['"])(?P<value>[^'"]{6,})\1""",
    re.IGNORECASE,
)

# A clearly-marked placeholder is the honest scaffold behaviour the Playwright
# agent is instructed to produce when a ticket supplies no real credentials.
# Flagging it would punish the agent for not inventing a secret.
_PLACEHOLDER_VALUE = re.compile(
    r"^\s*(?:<<.*>>|\{\{.*\}\}|\$\{.*\}|<[A-Z_ ]+>|%[A-Z_]+%|"
    r"(?:TODO|FIXME|PLACEHOLDER|REPLACE[_-]?ME|CHANGE[_-]?ME|YOUR[_-].*|"
    r"SET[_-]?ME|DUMMY|EXAMPLE|x{3,}|\.{3,})[^'\"]*)\s*$",
    re.IGNORECASE,
)


def _hard_coded_credentials(code: str) -> list[str]:
    """Return literal credential values, ignoring placeholders and env lookups."""
    found: list[str] = []
    for match in _CREDENTIAL_ASSIGNMENT.finditer(code):
        value = match.group("value")
        if _PLACEHOLDER_VALUE.match(value):
            continue
        if "process.env" in value or "${" in value:
            continue
        if value not in found:
            found.append(value)
    return found

_PLACEHOLDER = re.compile(
    r"(TODO|FIXME|PLACEHOLDER|REPLACE_ME|<your|CHANGE_ME|xxxxx)", re.IGNORECASE
)

_ID_PATTERNS = {
    "requirement": re.compile(r"^REQ-\d{3,}$"),
    "acceptance": re.compile(r"^AC-\d{3,}$"),
}


def _dupes(values: list[str]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes


def validate_analysis(payload: AnalysisPayload) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    stage = "analysis"

    reqs = list(payload.functional_requirements) + list(
        payload.non_functional_requirements
    )
    req_ids = [r.id for r in reqs]
    ac_ids = [ac.id for ac in payload.acceptance_criteria]

    if not reqs:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="no_requirements",
                message="The analyst produced no requirements.",
            )
        )

    for dup in _dupes(req_ids):
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="duplicate_requirement_id",
                message=f"Requirement id {dup} is used more than once.",
            )
        )
    for dup in _dupes(ac_ids):
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="duplicate_ac_id",
                message=f"Acceptance criterion id {dup} is used more than once.",
            )
        )

    for req in reqs:
        if not _ID_PATTERNS["requirement"].match(req.id):
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="requirement_id_format",
                    message=f"Requirement id {req.id!r} is not REQ-NNN.",
                )
            )
        if not req.text.strip():
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.ERROR,
                    code="empty_requirement",
                    message=f"Requirement {req.id} has no text.",
                )
            )
        if req.classification is InfoClass.EXPLICIT and not req.evidence.strip():
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="missing_evidence",
                    message=(
                        f"{req.id} is marked EXPLICIT but quotes no supporting "
                        "ticket text."
                    ),
                )
            )

    known_reqs = set(req_ids)
    for ac in payload.acceptance_criteria:
        if not _ID_PATTERNS["acceptance"].match(ac.id):
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="ac_id_format",
                    message=f"Acceptance criterion id {ac.id!r} is not AC-NNN.",
                )
            )
        unknown = [r for r in ac.requirement_ids if r not in known_reqs]
        if unknown:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="unknown_requirement_ref",
                    message=(
                        f"{ac.id} references unknown requirement(s): "
                        f"{', '.join(unknown)}."
                    ),
                )
            )

    return issues


def validate_test_plan(
    plan: TestPlan, analysis: RequirementAnalysis
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    stage = "test_plan"

    if len(plan.sections) != 12:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="section_count",
                message=(
                    f"Test plan has {len(plan.sections)} sections, expected 12."
                ),
            )
        )

    numbers = [s.number for s in plan.sections]
    for dup in _dupes([str(n) for n in numbers]):
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="duplicate_section",
                message=f"Section number {dup} appears more than once.",
            )
        )

    missing = [n for n in range(1, 13) if n not in numbers]
    if missing:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="missing_sections",
                message=(
                    "Missing section(s): "
                    + ", ".join(f"{n} {TEST_PLAN_SECTIONS[n - 1]}" for n in missing)
                ),
            )
        )

    for section in plan.sections:
        if not section.content.strip():
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.ERROR,
                    code="empty_section",
                    message=f"Section {section.number} ({section.title}) is empty.",
                )
            )

    known = set(analysis.requirement_ids) | set(analysis.acceptance_criteria_ids)
    for scenario in plan.scenarios:
        refs = list(scenario.requirement_ids) + list(scenario.acceptance_criteria_ids)
        if not refs:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="untraceable_scenario",
                    message=f"Scenario {scenario.id} references no REQ or AC id.",
                )
            )
        unknown = [r for r in refs if r not in known]
        if unknown:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="unknown_scenario_ref",
                    message=(
                        f"Scenario {scenario.id} references unknown id(s): "
                        f"{', '.join(unknown)}."
                    ),
                )
            )

    return issues


def validate_test_cases(
    suite: TestCaseSuite, analysis: RequirementAnalysis
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    stage = "test_cases"

    if not suite.test_cases:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="no_test_cases",
                message="No test cases were produced.",
            )
        )

    for dup in _dupes([tc.id for tc in suite.test_cases]):
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="duplicate_test_case_id",
                message=f"Test case id {dup} is used more than once.",
            )
        )

    known = set(analysis.requirement_ids) | set(analysis.acceptance_criteria_ids)
    prefix = f"{analysis.ticket_key}-TC-"

    for tc in suite.test_cases:
        if not tc.id.startswith(prefix):
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="test_case_id_format",
                    message=f"{tc.id} does not start with {prefix}.",
                )
            )
        if not tc.steps:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.ERROR,
                    code="no_steps",
                    message=f"{tc.id} has no steps.",
                )
            )
        if not tc.expected_result.strip():
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="no_expected_result",
                    message=f"{tc.id} has no expected result.",
                )
            )
        refs = list(tc.requirement_ids) + list(tc.acceptance_criteria_ids)
        if not refs:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="untraceable_test_case",
                    message=f"{tc.id} references no requirement or criterion.",
                )
            )
        unknown = [r for r in refs if r not in known]
        if unknown:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="unknown_test_case_ref",
                    message=(
                        f"{tc.id} references unknown id(s): {', '.join(unknown)}."
                    ),
                )
            )

    # Every EXPLICIT acceptance criterion needs at least one positive test.
    for ac in analysis.analysis.acceptance_criteria:
        if ac.classification is not InfoClass.EXPLICIT:
            continue
        linked = [tc for tc in suite.test_cases if ac.id in tc.acceptance_criteria_ids]
        if not linked:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="uncovered_acceptance_criterion",
                    message=f"{ac.id} has no test case.",
                )
            )

    return issues


def validate_playwright(
    bundle: PlaywrightBundle, suite: TestCaseSuite
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    stage = "playwright"

    automatable = {
        tc.id
        for tc in suite.test_cases
        if tc.automation_candidate
        in (AutomationCandidate.YES, AutomationCandidate.PARTIAL)
    }
    known_cases = {tc.id for tc in suite.test_cases}

    if automatable and not bundle.files:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.ERROR,
                code="no_files",
                message=(
                    f"{len(automatable)} test case(s) are automation candidates "
                    "but no Playwright file was produced."
                ),
            )
        )

    all_code = "\n".join(f.content for f in bundle.files)

    for pattern, description in _BANNED_CODE:
        if pattern.search(all_code):
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.ERROR,
                    code="banned_pattern",
                    message=f"Generated Playwright code {description}.",
                )
            )

    if all_code:
        for value in _hard_coded_credentials(all_code)[:3]:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.ERROR,
                    code="banned_pattern",
                    message=(
                        "Generated Playwright code appears to hard-code a "
                        f"credential ({value[:4]}...). Use process.env instead."
                    ),
                )
            )

    if all_code and "@playwright/test" not in all_code:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.WARNING,
                code="missing_import",
                message="No import from '@playwright/test' was found.",
            )
        )

    for mapping in bundle.mappings:
        if mapping.test_case_id not in known_cases:
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.WARNING,
                    code="unknown_mapping",
                    message=(
                        f"Mapping references unknown test case "
                        f"{mapping.test_case_id}."
                    ),
                )
            )

    # Readiness must be honest about placeholders.
    if bundle.readiness is AutomationReadiness.READY and _PLACEHOLDER.search(all_code):
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.WARNING,
                code="readiness_overclaim",
                message=(
                    "Readiness is READY but the code still contains placeholders. "
                    "Downgraded to NEEDS_CONFIGURATION."
                ),
            )
        )

    for file in bundle.files:
        if not file.content.strip():
            issues.append(
                ValidationIssue(
                    stage=stage,
                    severity=Severity.ERROR,
                    code="empty_file",
                    message=f"Generated file {file.path} is empty.",
                )
            )

    return issues


def validate_coverage(report: CoverageReport) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    stage = "coverage"

    for req_id in report.orphan_requirements:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.WARNING,
                code="orphan_requirement",
                message=f"{req_id} is not covered by any test case.",
            )
        )
    for tc_id in report.orphan_test_cases:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.WARNING,
                code="orphan_test_case",
                message=f"{tc_id} does not trace to any requirement.",
            )
        )
    for ref in report.unknown_requirement_refs:
        issues.append(
            ValidationIssue(
                stage=stage,
                severity=Severity.WARNING,
                code="unknown_reference",
                message=f"Test cases reference unknown id {ref}.",
            )
        )
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity is Severity.ERROR for i in issues)
