"""Structured-output recovery and the single controlled repair pass."""

from __future__ import annotations

import json

import pytest

from jira_qa_crew.exceptions import StructuredOutputError
from jira_qa_crew.models import AnalysisPayload, TestPlan
from jira_qa_crew.services.structured import extract_model


def test_populated_pydantic_field_is_used_directly(payload, fake_task_output) -> None:
    model, warnings = extract_model(
        fake_task_output(pydantic=payload), AnalysisPayload, stage="analysis"
    )
    assert model is payload
    assert warnings == []


def test_json_dict_is_used_when_pydantic_is_empty(payload, fake_task_output) -> None:
    output = fake_task_output(pydantic=None, json_dict=payload.model_dump(mode="json"))
    model, warnings = extract_model(output, AnalysisPayload, stage="analysis")

    assert len(model.functional_requirements) == 2
    assert any("json_dict" in w for w in warnings)


def test_raw_json_is_salvaged(payload, fake_task_output) -> None:
    raw = json.dumps(payload.model_dump(mode="json"))
    model, warnings = extract_model(
        fake_task_output(raw=raw), AnalysisPayload, stage="analysis"
    )

    assert len(model.functional_requirements) == 2
    assert any("repaired" in w for w in warnings)


def test_json_inside_a_code_fence_is_salvaged(payload, fake_task_output) -> None:
    raw = (
        "Here is the analysis you asked for:\n\n```json\n"
        + json.dumps(payload.model_dump(mode="json"))
        + "\n```\nLet me know if you need changes."
    )
    model, _ = extract_model(
        fake_task_output(raw=raw), AnalysisPayload, stage="analysis"
    )
    assert len(model.functional_requirements) == 2


def test_json_surrounded_by_prose_is_salvaged(payload, fake_task_output) -> None:
    raw = "Sure! " + json.dumps(payload.model_dump(mode="json")) + " Hope that helps."
    model, _ = extract_model(
        fake_task_output(raw=raw), AnalysisPayload, stage="analysis"
    )
    assert len(model.functional_requirements) == 2


def test_unparseable_output_raises_rather_than_guessing(fake_task_output) -> None:
    with pytest.raises(StructuredOutputError) as excinfo:
        extract_model(
            fake_task_output(raw="I could not complete this task."),
            AnalysisPayload,
            stage="analysis",
        )
    assert "analysis" in str(excinfo.value)


def test_wrong_schema_raises(fake_task_output) -> None:
    """A TestPlan payload must not be accepted where sections are required."""
    with pytest.raises(StructuredOutputError):
        extract_model(
            fake_task_output(raw=json.dumps({"sections": "not-a-list"})),
            TestPlan,
            stage="test_plan",
        )


def test_empty_output_raises(fake_task_output) -> None:
    with pytest.raises(StructuredOutputError):
        extract_model(fake_task_output(raw=""), AnalysisPayload, stage="analysis")


def test_json_array_wrapper_is_unwrapped(payload, fake_task_output) -> None:
    raw = json.dumps([payload.model_dump(mode="json")])
    model, _ = extract_model(
        fake_task_output(raw=raw), AnalysisPayload, stage="analysis"
    )
    assert len(model.functional_requirements) == 2


def test_salvage_is_bounded_and_never_calls_a_model(fake_task_output) -> None:
    """The repair pass is pure parsing, so it cannot loop or cost a request."""
    calls: list[int] = []

    class CountingOutput:
        pydantic = None
        json_dict = None

        @property
        def raw(self):
            calls.append(1)
            return "not json at all"

    with pytest.raises(StructuredOutputError):
        extract_model(CountingOutput(), AnalysisPayload, stage="analysis")

    assert len(calls) == 1
