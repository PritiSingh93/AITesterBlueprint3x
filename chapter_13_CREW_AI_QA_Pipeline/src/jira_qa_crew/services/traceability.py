"""Coverage and traceability, computed deterministically in Python.

An LLM is never asked how well it covered the requirements, because a model
grading its own output is not evidence.
"""

from __future__ import annotations

from ..models import (
    AutomationCandidate,
    CoverageReport,
    CoverageStatus,
    PlaywrightBundle,
    RequirementAnalysis,
    TestCaseSuite,
    TraceabilityRow,
)


def build_coverage(
    analysis: RequirementAnalysis,
    suite: TestCaseSuite | None,
    bundle: PlaywrightBundle | None,
) -> CoverageReport:
    """Map every requirement and acceptance criterion to the tests covering it."""
    test_cases = list(suite.test_cases) if suite else []
    automated_ids = {m.test_case_id for m in (bundle.mappings if bundle else [])}

    req_ids = list(dict.fromkeys(analysis.requirement_ids))
    ac_ids = list(dict.fromkeys(analysis.acceptance_criteria_ids))
    known_ids = set(req_ids) | set(ac_ids)

    ac_to_reqs: dict[str, list[str]] = {
        ac.id: list(ac.requirement_ids) for ac in analysis.analysis.acceptance_criteria
    }

    rows: list[TraceabilityRow] = []
    covered_reqs: set[str] = set()
    covered_acs: set[str] = set()
    referenced_ids: set[str] = set()
    linked_case_ids: set[str] = set()

    # One row per acceptance criterion, then a row for any requirement that has
    # no criterion of its own.
    for ac_id in ac_ids:
        parents = ac_to_reqs.get(ac_id) or []
        matching = [
            tc
            for tc in test_cases
            if ac_id in tc.acceptance_criteria_ids
            or any(p in tc.requirement_ids for p in parents)
        ]
        for tc in matching:
            referenced_ids.update(tc.requirement_ids)
            referenced_ids.update(tc.acceptance_criteria_ids)
            linked_case_ids.add(tc.id)

        case_ids = [tc.id for tc in matching]
        auto_ids = [tc_id for tc_id in case_ids if tc_id in automated_ids]
        status, reason = _status_for(matching, auto_ids)
        if status is not CoverageStatus.NONE:
            covered_acs.add(ac_id)
            covered_reqs.update(parents)

        rows.append(
            TraceabilityRow(
                requirement_id=", ".join(parents) or "(unlinked)",
                acceptance_criterion_id=ac_id,
                test_case_ids=case_ids,
                automated_test_case_ids=auto_ids,
                coverage_status=status,
                reason=reason,
            )
        )

    acs_with_parents = {r for parents in ac_to_reqs.values() for r in parents}
    for req_id in req_ids:
        if req_id in acs_with_parents:
            continue
        matching = [tc for tc in test_cases if req_id in tc.requirement_ids]
        for tc in matching:
            referenced_ids.update(tc.requirement_ids)
            referenced_ids.update(tc.acceptance_criteria_ids)
            linked_case_ids.add(tc.id)
        case_ids = [tc.id for tc in matching]
        auto_ids = [tc_id for tc_id in case_ids if tc_id in automated_ids]
        status, reason = _status_for(matching, auto_ids)
        if status is not CoverageStatus.NONE:
            covered_reqs.add(req_id)
        rows.append(
            TraceabilityRow(
                requirement_id=req_id,
                acceptance_criterion_id="",
                test_case_ids=case_ids,
                automated_test_case_ids=auto_ids,
                coverage_status=status,
                reason=reason,
            )
        )

    orphan_cases = [
        tc.id
        for tc in test_cases
        if not tc.requirement_ids and not tc.acceptance_criteria_ids
    ]
    orphan_cases += [
        tc.id
        for tc in test_cases
        if tc.id not in linked_case_ids and tc.id not in orphan_cases
    ]

    return CoverageReport(
        rows=rows,
        orphan_requirements=[r for r in req_ids if r not in covered_reqs],
        orphan_acceptance_criteria=[a for a in ac_ids if a not in covered_acs],
        orphan_test_cases=sorted(set(orphan_cases)),
        unknown_requirement_refs=sorted(referenced_ids - known_ids),
        total_requirements=len(req_ids),
        covered_requirements=len(covered_reqs & set(req_ids)),
        total_acceptance_criteria=len(ac_ids),
        covered_acceptance_criteria=len(covered_acs),
        total_test_cases=len(test_cases),
        automated_test_cases=len(
            [tc for tc in test_cases if tc.id in automated_ids]
        ),
    )


def _status_for(matching: list, auto_ids: list[str]) -> tuple[CoverageStatus, str]:
    if not matching:
        return CoverageStatus.NONE, "No test case references this item."

    has_positive = any(
        tc.automation_candidate is not None and _is_positive(tc) for tc in matching
    )
    has_negative = any(_is_negative(tc) for tc in matching)

    if not auto_ids:
        reason = "Covered by manual test cases only."
    elif len(auto_ids) < len(matching):
        reason = f"{len(auto_ids)} of {len(matching)} cases automated."
    else:
        reason = "All linked cases are automated."

    if has_positive and has_negative:
        return CoverageStatus.COVERED, reason
    missing = "negative or boundary" if has_positive else "positive"
    return CoverageStatus.PARTIAL, f"{reason} Missing a {missing} case."


def _is_negative(test_case) -> bool:
    haystack = " ".join(
        [test_case.test_type or "", test_case.title or "", " ".join(test_case.tags)]
    ).lower()
    return any(
        token in haystack
        for token in ("negative", "boundary", "invalid", "error", "edge")
    )


def _is_positive(test_case) -> bool:
    return not _is_negative(test_case)


def automated_case_ids(bundle: PlaywrightBundle | None) -> set[str]:
    return {m.test_case_id for m in (bundle.mappings if bundle else [])}


def automatable_cases(suite: TestCaseSuite | None) -> list[str]:
    if not suite:
        return []
    return [
        tc.id
        for tc in suite.test_cases
        if tc.automation_candidate
        in (AutomationCandidate.YES, AutomationCandidate.PARTIAL)
    ]
