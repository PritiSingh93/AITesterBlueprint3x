"""Stage progress tracking.

Progress reflects real task completion reported by CrewAI. Nothing here
simulates token-level streaming.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from ..logging_utils import get_logger
from ..models import StageProgress, StageState

logger = get_logger("crew.callbacks")

STAGE_NAMES: tuple[str, ...] = (
    "Jira Analyst",
    "Test Plan Writer",
    "Test Case Writer",
    "Playwright Coder",
)

ProgressHook = Callable[[str, "ProgressTracker"], None]


class ProgressTracker:
    """Track the four pipeline stages for one ticket."""

    def __init__(
        self,
        ticket_key: str,
        on_update: ProgressHook | None = None,
        stage_names: tuple[str, ...] = STAGE_NAMES,
    ) -> None:
        self.ticket_key = ticket_key
        self._on_update = on_update
        self.stages: list[StageProgress] = [
            StageProgress(name=name) for name in stage_names
        ]

    def _find(self, name: str) -> StageProgress | None:
        return next((s for s in self.stages if s.name == name), None)

    def _emit(self) -> None:
        if self._on_update is None:
            return
        try:
            self._on_update(self.ticket_key, self)
        except Exception:
            # A UI refresh failure must never abort the pipeline.
            logger.exception("Progress hook failed for %s", self.ticket_key)

    def start(self, name: str, message: str = "") -> None:
        stage = self._find(name)
        if stage is None:
            return
        stage.state = StageState.RUNNING
        stage.message = message or "Running"
        stage.started_at = datetime.now(UTC)
        logger.info("[%s] %s started", self.ticket_key, name)
        self._emit()

    def finish(
        self, name: str, state: StageState = StageState.COMPLETED, message: str = ""
    ) -> None:
        stage = self._find(name)
        if stage is None:
            return
        stage.state = state
        stage.message = message or state.value.title()
        stage.finished_at = datetime.now(UTC)
        logger.info("[%s] %s -> %s", self.ticket_key, name, state.value)
        self._emit()

    def fail_remaining(self, message: str) -> None:
        """Mark every stage that never ran as failed."""
        for stage in self.stages:
            if stage.state in (StageState.PENDING, StageState.RUNNING):
                stage.state = StageState.FAILED
                stage.message = message
                stage.finished_at = datetime.now(UTC)
        self._emit()

    @property
    def completed_count(self) -> int:
        return sum(
            1
            for s in self.stages
            if s.state in (StageState.COMPLETED, StageState.WARNING)
        )

    def snapshot(self) -> list[StageProgress]:
        return [s.model_copy(deep=True) for s in self.stages]
