"""Pydantic domain models.

Design note: Jira *facts* (key, summary, status, priority, labels, ...) are never
produced by an LLM. They are read from the Jira provider and carried in
:class:`JiraIssue`. An LLM only ever produces *analysis* (:class:`AnalysisPayload`,
:class:`TestPlan`, :class:`TestCaseSuite`, :class:`PlaywrightBundle`). The two are
merged in Python by :class:`RequirementAnalysis`, so a hallucinated ticket field
cannot reach an artifact.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InfoClass(StrEnum):
    """How a piece of information relates to the source ticket."""

    EXPLICIT = "EXPLICIT"
    INFERRED = "INFERRED"
    MISSING = "MISSING"
    ASSUMPTION_REQUIRING_CONFIRMATION = "ASSUMPTION_REQUIRING_CONFIRMATION"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class AutomationCandidate(StrEnum):
    YES = "Yes"
    NO = "No"
    PARTIAL = "Partial"


class AutomationReadiness(StrEnum):
    READY = "READY"
    NEEDS_CONFIGURATION = "NEEDS_CONFIGURATION"
    NOT_AUTOMATED = "NOT_AUTOMATED"


class ProviderSource(StrEnum):
    MCP = "MCP"
    REST = "REST"
    FIXTURE = "FIXTURE"


class TicketOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    # Some stages produced usable output before a later one failed. Never
    # reported as success, but the work that did complete is kept and shown.
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class StageState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    WARNING = "WARNING"
    FAILED = "FAILED"


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class CoverageStatus(StrEnum):
    COVERED = "COVERED"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


# --------------------------------------------------------------------------
# Deterministic Jira facts
# --------------------------------------------------------------------------


class JiraIssue(BaseModel):
    """A Jira issue exactly as read from a provider. Never LLM-generated."""

    model_config = ConfigDict(extra="ignore")

    key: str
    summary: str = ""
    description: str = ""
    issue_type: str = "Unknown"
    status: str = "Unknown"
    priority: str = "Not set"
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    parent: str | None = None
    subtasks: list[str] = Field(default_factory=list)
    linked_issues: list[str] = Field(default_factory=list)
    acceptance_criteria_raw: str = ""
    comments: list[str] = Field(default_factory=list)
    url: str = ""
    source: ProviderSource = ProviderSource.REST
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def as_prompt_block(self) -> str:
        """Render the issue as untrusted text for an LLM prompt."""
        parts = [
            f"Ticket Key: {self.key}",
            f"Summary: {self.summary}",
            f"Issue Type: {self.issue_type}",
            f"Status: {self.status}",
            f"Priority: {self.priority}",
            f"Labels: {', '.join(self.labels) or 'None'}",
            f"Components: {', '.join(self.components) or 'None'}",
            f"Parent: {self.parent or 'None'}",
            f"Subtasks: {', '.join(self.subtasks) or 'None'}",
            f"Linked Issues: {', '.join(self.linked_issues) or 'None'}",
            "",
            "Description:",
            self.description or "(empty)",
        ]
        if self.acceptance_criteria_raw:
            parts += ["", "Acceptance Criteria field:", self.acceptance_criteria_raw]
        if self.comments:
            parts += ["", "Comments:"] + [f"- {c}" for c in self.comments]
        return "\n".join(parts)


# --------------------------------------------------------------------------
# Stage 1 - analysis
# --------------------------------------------------------------------------


class Requirement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Stable id such as REQ-001")
    text: str
    classification: InfoClass = InfoClass.EXPLICIT
    evidence: str = Field(
        default="",
        description="Short quote from the ticket supporting this requirement.",
    )


class AcceptanceCriterion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Stable id such as AC-001")
    text: str
    classification: InfoClass = InfoClass.EXPLICIT
    requirement_ids: list[str] = Field(default_factory=list)
    evidence: str = ""


class AnalysisPayload(BaseModel):
    """Structured output of the Jira Analyst agent."""

    model_config = ConfigDict(extra="ignore")

    functional_requirements: list[Requirement] = Field(default_factory=list)
    non_functional_requirements: list[Requirement] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class RequirementAnalysis(BaseModel):
    """Deterministic Jira facts merged with the agent's analysis."""

    model_config = ConfigDict(extra="ignore")

    issue: JiraIssue
    analysis: AnalysisPayload

    @property
    def ticket_key(self) -> str:
        return self.issue.key

    @property
    def all_requirements(self) -> list[Requirement]:
        return list(self.analysis.functional_requirements) + list(
            self.analysis.non_functional_requirements
        )

    @property
    def requirement_ids(self) -> list[str]:
        return [r.id for r in self.all_requirements]

    @property
    def acceptance_criteria_ids(self) -> list[str]:
        return [ac.id for ac in self.analysis.acceptance_criteria]


# --------------------------------------------------------------------------
# Stage 2 - test plan
# --------------------------------------------------------------------------

TEST_PLAN_SECTIONS: tuple[str, ...] = (
    "Executive Summary",
    "Test Objectives",
    "In Scope",
    "Out of Scope",
    "Requirements and Acceptance-Criteria Coverage",
    "Test Strategy, Levels, and Test Types",
    "Test Environment, Tools, and Browser Coverage",
    "Test Data Requirements",
    "High-Level Test Scenarios",
    "Entry and Exit Criteria",
    "Risks, Dependencies, Assumptions, and Mitigations",
    "Execution, Defect Management, Reporting, and Deliverables",
)


class TestPlanSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int = Field(ge=1, le=12)
    title: str
    content: str


class TestScenario(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Stable id such as SC-001")
    title: str
    description: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    acceptance_criteria_ids: list[str] = Field(default_factory=list)


class TestPlan(BaseModel):
    """Structured output of the Test Plan Writer agent."""

    model_config = ConfigDict(extra="ignore")

    sections: list[TestPlanSection] = Field(default_factory=list)
    scenarios: list[TestScenario] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Stage 3 - test cases
# --------------------------------------------------------------------------


class TestStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int = Field(ge=1)
    action: str
    expected: str = ""


class TestCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Such as QATEST-7-TC-001")
    requirement_ids: list[str] = Field(default_factory=list)
    acceptance_criteria_ids: list[str] = Field(default_factory=list)
    title: str
    objective: str = ""
    priority: Priority = Priority.P2
    test_type: str = "Functional"
    preconditions: list[str] = Field(default_factory=list)
    test_data: list[str] = Field(default_factory=list)
    steps: list[TestStep] = Field(default_factory=list)
    expected_result: str = ""
    automation_candidate: AutomationCandidate = AutomationCandidate.NO
    automation_rationale: str = ""
    tags: list[str] = Field(default_factory=list)
    assumptions_or_blockers: list[str] = Field(default_factory=list)

    @field_validator("priority", mode="before")
    @classmethod
    def _coerce_priority(cls, value: object) -> object:
        if isinstance(value, str):
            token = value.strip().upper()
            for member in Priority:
                if token.startswith(member.value):
                    return member
        return value

    @field_validator("automation_candidate", mode="before")
    @classmethod
    def _coerce_candidate(cls, value: object) -> object:
        if isinstance(value, str):
            token = value.strip().lower()
            mapping = {
                "yes": AutomationCandidate.YES,
                "true": AutomationCandidate.YES,
                "no": AutomationCandidate.NO,
                "false": AutomationCandidate.NO,
                "partial": AutomationCandidate.PARTIAL,
            }
            if token in mapping:
                return mapping[token]
        return value


class TestCaseSuite(BaseModel):
    """Structured output of the Test Case Writer agent."""

    model_config = ConfigDict(extra="ignore")

    test_cases: list[TestCase] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Stage 4 - playwright
# --------------------------------------------------------------------------


class PlaywrightFile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = Field(description="Repo-relative path, e.g. tests/qatest-7.spec.ts")
    content: str


class AutomatedTestMapping(BaseModel):
    model_config = ConfigDict(extra="ignore")

    test_case_id: str
    test_name: str
    requirement_ids: list[str] = Field(default_factory=list)
    acceptance_criteria_ids: list[str] = Field(default_factory=list)


class PlaywrightBundle(BaseModel):
    """Structured output of the Playwright Coder agent."""

    model_config = ConfigDict(extra="ignore")

    files: list[PlaywrightFile] = Field(default_factory=list)
    mappings: list[AutomatedTestMapping] = Field(default_factory=list)
    readiness: AutomationReadiness = AutomationReadiness.NEEDS_CONFIGURATION
    setup_notes: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Traceability (computed in Python, never by an LLM)
# --------------------------------------------------------------------------


class TraceabilityRow(BaseModel):
    requirement_id: str
    acceptance_criterion_id: str = ""
    test_case_ids: list[str] = Field(default_factory=list)
    automated_test_case_ids: list[str] = Field(default_factory=list)
    coverage_status: CoverageStatus = CoverageStatus.NONE
    reason: str = ""


class CoverageReport(BaseModel):
    rows: list[TraceabilityRow] = Field(default_factory=list)
    orphan_requirements: list[str] = Field(default_factory=list)
    orphan_acceptance_criteria: list[str] = Field(default_factory=list)
    orphan_test_cases: list[str] = Field(default_factory=list)
    unknown_requirement_refs: list[str] = Field(default_factory=list)
    total_requirements: int = 0
    covered_requirements: int = 0
    total_acceptance_criteria: int = 0
    covered_acceptance_criteria: int = 0
    total_test_cases: int = 0
    automated_test_cases: int = 0

    @property
    def requirement_coverage_pct(self) -> float:
        if not self.total_requirements:
            return 0.0
        return round(100 * self.covered_requirements / self.total_requirements, 1)

    @property
    def acceptance_criteria_coverage_pct(self) -> float:
        if not self.total_acceptance_criteria:
            return 0.0
        return round(
            100 * self.covered_acceptance_criteria / self.total_acceptance_criteria, 1
        )


# --------------------------------------------------------------------------
# Validation + run bookkeeping
# --------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    stage: str
    severity: Severity
    code: str
    message: str


class StageProgress(BaseModel):
    name: str
    state: StageState = StageState.PENDING
    message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 2)
        return None


class TicketResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    ticket_key: str
    outcome: TicketOutcome = TicketOutcome.FAILED
    source: ProviderSource | None = None
    issue: JiraIssue | None = None
    analysis: RequirementAnalysis | None = None
    test_plan: TestPlan | None = None
    test_cases: TestCaseSuite | None = None
    playwright: PlaywrightBundle | None = None
    coverage: CoverageReport | None = None
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    stages: list[StageProgress] = Field(default_factory=list)
    error: str = ""
    # The provider's own words, redacted. ``error`` is this app's reading of
    # them, which can be wrong; keeping both means a misreading is visible
    # instead of being the only account of what happened.
    error_detail: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    artifact_dir: str = ""
    artifacts: dict[str, str] = Field(default_factory=dict)

    @property
    def automation_readiness(self) -> AutomationReadiness:
        if self.playwright is None:
            return AutomationReadiness.NOT_AUTOMATED
        return self.playwright.readiness

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 2)
        return None


class RunResult(BaseModel):
    run_id: str
    requested_tickets: list[str] = Field(default_factory=list)
    results: list[TicketResult] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output_dir: str = ""

    @property
    def completed(self) -> list[TicketResult]:
        return [r for r in self.results if r.outcome is TicketOutcome.COMPLETED]

    @property
    def with_warnings(self) -> list[TicketResult]:
        return [
            r for r in self.results if r.outcome is TicketOutcome.COMPLETED_WITH_WARNINGS
        ]

    @property
    def partial(self) -> list[TicketResult]:
        return [r for r in self.results if r.outcome is TicketOutcome.PARTIAL]

    @property
    def failed(self) -> list[TicketResult]:
        return [r for r in self.results if r.outcome is TicketOutcome.FAILED]

    @property
    def successful(self) -> bool:
        """A run succeeds when at least one ticket produced usable output.

        Partial tickets count: a requirements analysis and a test plan are
        worth reviewing even when the automation stage did not finish.
        """
        return bool(self.completed or self.with_warnings or self.partial)
