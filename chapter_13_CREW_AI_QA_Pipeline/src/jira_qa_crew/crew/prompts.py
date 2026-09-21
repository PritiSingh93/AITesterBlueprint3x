"""Load agent and task prompts from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import yaml

from ..exceptions import ConfigurationError

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=4)
def _load(filename: str) -> dict[str, Any]:
    path = PROMPTS_DIR / filename
    if not path.is_file():
        raise ConfigurationError(f"Prompt file missing: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigurationError(f"Prompt file {path} must contain a mapping.")
    return data


def agent_prompt(key: str, **values: str) -> dict[str, str]:
    """Return role/goal/backstory for an agent, with placeholders filled."""
    spec = _load("agents.yaml").get(key)
    if not isinstance(spec, dict):
        raise ConfigurationError(f"No agent prompt named {key!r} in agents.yaml")
    return {
        field: Template(str(spec.get(field, ""))).safe_substitute(**values).strip()
        for field in ("role", "goal", "backstory")
    }


def task_prompt(key: str, **values: str) -> dict[str, str]:
    """Return description/expected_output for a task, with placeholders filled."""
    spec = _load("tasks.yaml").get(key)
    if not isinstance(spec, dict):
        raise ConfigurationError(f"No task prompt named {key!r} in tasks.yaml")
    return {
        field: Template(str(spec.get(field, ""))).safe_substitute(**values).strip()
        for field in ("description", "expected_output")
    }
