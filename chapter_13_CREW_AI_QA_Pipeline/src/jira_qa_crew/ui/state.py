"""Streamlit session state.

Results live in ``st.session_state`` so a completed run survives the reruns
Streamlit performs on every widget interaction.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from ..crew.callbacks import ProgressTracker
from ..models import RunResult

_KEYS = {
    "run_result": None,
    "progress": {},
    "running": False,
    "last_error": "",
    "ticket_input": "",
    "integration_mode": "auto",
    "zip_bytes": None,
}


def init_state() -> None:
    for key, default in _KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = default() if callable(default) else default


def get(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


def set_value(key: str, value: Any) -> None:
    st.session_state[key] = value


def set_run_result(run: RunResult | None) -> None:
    st.session_state["run_result"] = run
    # A new run invalidates any archive built for the previous one.
    st.session_state["zip_bytes"] = None


def get_run_result() -> RunResult | None:
    return st.session_state.get("run_result")


def record_progress(ticket_key: str, tracker: ProgressTracker) -> None:
    """Store a snapshot of one ticket's stage progress."""
    progress = dict(st.session_state.get("progress") or {})
    progress[ticket_key] = tracker.snapshot()
    st.session_state["progress"] = progress


def reset_progress() -> None:
    st.session_state["progress"] = {}


def get_progress() -> dict[str, list]:
    return st.session_state.get("progress") or {}
