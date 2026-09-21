"""Shared test fixtures.

No test in the default suite touches a real Jira instance or a paid LLM.
"""

from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

import pytest

from jira_qa_crew.config import load_config
from jira_qa_crew.models import (
    AcceptanceCriterion,
    AnalysisPayload,
    AutomatedTestMapping,
    AutomationCandidate,
    AutomationReadiness,
    InfoClass,
    JiraIssue,
    PlaywrightBundle,
    PlaywrightFile,
    Priority,
    ProviderSource,
    Requirement,
    RequirementAnalysis,
    TestCase,
    TestCaseSuite,
    TestPlan,
    TestPlanSection,
    TestScenario,
    TestStep,
)

TICKET = "QATEST-7"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from a known, credential-free environment."""
    for key in list(os.environ):
        if key.startswith(("JIRA_", "LLM_", "PIPELINE_", "DEMO_", "APP_", "OUTPUT_")):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def base_config():
    cfg = load_config()
    return replace(
        cfg,
        llm=replace(cfg.llm, model="test/model", api_key="test-key"),
        rest=replace(
            cfg.rest,
            url="https://example.atlassian.net",
            email="qa@example.com",
            api_token="token-value-1234",
        ),
    )


@pytest.fixture
def issue() -> JiraIssue:
    return JiraIssue(
        key=TICKET,
        summary="Cart total shows $0.00 after applying a discount code",
        description="Applying SAVE20 to a cart of 3+ items shows $0.00.",
        issue_type="Bug",
        status="Open",
        priority="High",
        labels=["checkout"],
        components=["Cart"],
        url="https://example.atlassian.net/browse/QATEST-7",
        source=ProviderSource.REST,
    )


@pytest.fixture
def payload() -> AnalysisPayload:
    return AnalysisPayload(
        functional_requirements=[
            Requirement(
                id="REQ-001",
                text="Cart total must equal subtotal minus the discount.",
                classification=InfoClass.EXPLICIT,
                evidence="Expected Result: subtotal minus 20%.",
            ),
            Requirement(
                id="REQ-002",
                text="Displayed total must match the pricing API response.",
                classification=InfoClass.EXPLICIT,
                evidence="The pricing API response contains the correct amount.",
            ),
        ],
        non_functional_requirements=[],
        acceptance_criteria=[
            AcceptanceCriterion(
                id="AC-001",
                text="SAVE20 on any cart size shows subtotal minus 20%.",
                requirement_ids=["REQ-001"],
                classification=InfoClass.EXPLICIT,
                evidence="Applying SAVE20 shows subtotal minus 20%.",
            ),
            AcceptanceCriterion(
                id="AC-002",
                text="Displayed total matches the API total.",
                requirement_ids=["REQ-002"],
                classification=InfoClass.EXPLICIT,
                evidence="API response shows the correct discounted amount.",
            ),
        ],
        risks=["Revenue impact if totals render as zero."],
        missing_information=["No selector or test URL supplied in the ticket."],
    )


@pytest.fixture
def analysis(issue: JiraIssue, payload: AnalysisPayload) -> RequirementAnalysis:
    return RequirementAnalysis(issue=issue, analysis=payload)


@pytest.fixture
def plan() -> TestPlan:
    from jira_qa_crew.models import TEST_PLAN_SECTIONS

    return TestPlan(
        sections=[
            TestPlanSection(number=i + 1, title=title, content=f"Content for {title}.")
            for i, title in enumerate(TEST_PLAN_SECTIONS)
        ],
        scenarios=[
            TestScenario(
                id="SC-001",
                title="Discount applies correctly at every cart size",
                requirement_ids=["REQ-001"],
                acceptance_criteria_ids=["AC-001"],
            )
        ],
    )


def _case(
    number: int,
    *,
    reqs: list[str],
    acs: list[str],
    title: str = "Apply discount",
    test_type: str = "Functional",
    candidate: AutomationCandidate = AutomationCandidate.YES,
) -> TestCase:
    return TestCase(
        id=f"{TICKET}-TC-{number:03d}",
        requirement_ids=reqs,
        acceptance_criteria_ids=acs,
        title=title,
        objective="Verify discount behaviour.",
        priority=Priority.P1,
        test_type=test_type,
        preconditions=["Cart contains 3 items"],
        test_data=["SAVE20"],
        steps=[TestStep(number=1, action="Apply SAVE20", expected="Total updates")],
        expected_result="Total equals subtotal minus 20%.",
        automation_candidate=candidate,
        automation_rationale="Deterministic UI assertion.",
        tags=["cart"],
    )


@pytest.fixture
def suite() -> TestCaseSuite:
    return TestCaseSuite(
        test_cases=[
            _case(1, reqs=["REQ-001"], acs=["AC-001"]),
            _case(
                2,
                reqs=["REQ-001"],
                acs=["AC-001"],
                title="Invalid discount code is rejected",
                test_type="Negative",
            ),
            _case(3, reqs=["REQ-002"], acs=["AC-002"], title="Total matches API"),
            _case(
                4,
                reqs=["REQ-002"],
                acs=["AC-002"],
                title="Boundary: cart of exactly 3 items",
                test_type="Boundary",
                candidate=AutomationCandidate.PARTIAL,
            ),
        ]
    )


@pytest.fixture
def bundle() -> PlaywrightBundle:
    code = (
        "import { test, expect } from '@playwright/test';\n\n"
        "// QATEST-7 | QATEST-7-TC-001 | REQ-001 | AC-001\n"
        "test('discount applies', async ({ page }) => {\n"
        "  await page.goto('/cart');\n"
        "  await expect(page.getByTestId('cart-total')).not.toHaveText('$0.00');\n"
        "});\n"
    )
    return PlaywrightBundle(
        files=[PlaywrightFile(path="tests/qatest-7.spec.ts", content=code)],
        mappings=[
            AutomatedTestMapping(
                test_case_id=f"{TICKET}-TC-001",
                test_name="discount applies",
                requirement_ids=["REQ-001"],
                acceptance_criteria_ids=["AC-001"],
            )
        ],
        readiness=AutomationReadiness.NEEDS_CONFIGURATION,
        setup_notes=["Set baseURL in playwright.config.ts."],
        missing_information=["Real cart page selectors."],
    )


class FakeTaskOutput:
    """Stand-in for crewai's TaskOutput."""

    def __init__(
        self,
        pydantic: Any = None,
        raw: str = "",
        json_dict: dict | None = None,
    ) -> None:
        self.pydantic = pydantic
        self.raw = raw
        self.json_dict = json_dict


class FakeCrewOutput:
    def __init__(self, tasks_output: list[Any]) -> None:
        self.tasks_output = tasks_output
        self.token_usage = None


@pytest.fixture
def fake_task_output():
    return FakeTaskOutput


@pytest.fixture
def fake_crew_output():
    return FakeCrewOutput
