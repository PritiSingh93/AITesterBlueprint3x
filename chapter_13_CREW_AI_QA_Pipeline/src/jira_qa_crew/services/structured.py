"""Recover a validated Pydantic object from a CrewAI task output.

CrewAI normally populates ``TaskOutput.pydantic``. When a model wraps its JSON in
prose or a code fence, that field is ``None`` and the stage would fail. One
deterministic salvage pass runs here instead of asking the model again: a retry
costs another full request and can loop, whereas parsing is bounded and free.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from ..exceptions import StructuredOutputError
from ..logging_utils import get_logger

logger = get_logger("services.structured")

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def _candidate_payloads(raw: str) -> list[str]:
    """Ordered candidates to try parsing, cheapest first."""
    candidates: list[str] = []
    text = (raw or "").strip()
    if not text:
        return candidates

    candidates.append(text)
    candidates.extend(match.strip() for match in _FENCE.findall(text))

    # Widest balanced-looking object in the text.
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1])

    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def extract_model(
    task_output: Any,
    model_cls: type[T],
    *,
    stage: str,
) -> tuple[T, list[str]]:
    """Return a validated model plus any warnings raised while recovering it.

    Raises :class:`StructuredOutputError` when nothing usable can be recovered.
    """
    warnings: list[str] = []

    direct = getattr(task_output, "pydantic", None)
    if isinstance(direct, model_cls):
        return direct, warnings

    json_dict = getattr(task_output, "json_dict", None)
    if isinstance(json_dict, dict):
        try:
            model = model_cls.model_validate(json_dict)
            warnings.append(
                f"{stage}: recovered structured output from json_dict "
                "(pydantic field was empty)."
            )
            return model, warnings
        except ValidationError as exc:
            logger.debug("%s json_dict did not validate: %s", stage, exc)

    raw = getattr(task_output, "raw", None) or str(task_output or "")
    errors: list[str] = []
    for candidate in _candidate_payloads(raw):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(f"json: {exc.msg}")
            continue
        if isinstance(data, list):
            data = next((d for d in data if isinstance(d, dict)), None)
        if not isinstance(data, dict):
            errors.append("payload was not a JSON object")
            continue
        try:
            model = model_cls.model_validate(data)
        except ValidationError as exc:
            errors.append(f"schema: {exc.error_count()} error(s)")
            continue
        warnings.append(
            f"{stage}: repaired malformed structured output by parsing the raw "
            "response (one salvage pass, no model retry)."
        )
        return model, warnings

    detail = "; ".join(errors[:3]) or "no JSON found in the response"
    raise StructuredOutputError(
        f"{stage} did not return valid {model_cls.__name__} output ({detail})."
    )
