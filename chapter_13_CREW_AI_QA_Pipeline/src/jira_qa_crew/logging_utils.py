"""Structured logging with secret redaction.

Every log record and every user-visible error string passes through
:func:`redact`, so an API token cannot reach a log file, the Streamlit UI, or a
generated artifact.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from .config import SECRET_KEYS

_REDACTED = "***REDACTED***"

# Token shapes that are recognisable on their own, even when the value never
# passed through a configured environment variable.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ATATT[A-Za-z0-9_\-=.]{10,}"),  # Atlassian API token
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),  # Groq
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),  # OpenAI style
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]{16,}=*", re.IGNORECASE),
    re.compile(r"Basic\s+[A-Za-z0-9+/]{16,}=*"),
)

_MIN_SECRET_LEN = 6


def _secret_values() -> list[str]:
    values: list[str] = []
    for key in SECRET_KEYS:
        raw = os.getenv(key, "")
        if raw and len(raw) >= _MIN_SECRET_LEN:
            values.append(raw)
    return values


def redact(text: Any) -> str:
    """Replace known secret values and secret-shaped tokens with a placeholder."""
    if text is None:
        return ""
    value = str(text)
    for secret in _secret_values():
        if secret in value:
            value = value.replace(secret, _REDACTED)
    for pattern in _PATTERNS:
        value = pattern.sub(_REDACTED, value)
    return value


def mask(value: str, keep: int = 4) -> str:
    """Render a configured secret for display, e.g. ``ATAT…9f2c``."""
    if not value:
        return "(not set)"
    if len(value) <= keep * 2:
        return _REDACTED
    return f"{value[:keep]}…{value[-keep:]}"


class RedactingFilter(logging.Filter):
    """Scrub secrets from the formatted message and its arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact(a) for a in record.args)
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            record.exc_text = redact("".join(map(str, exc.args)))
        return True


_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Install a redacting stream handler once per process."""
    global _CONFIGURED
    root = logging.getLogger("jira_qa_crew")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if _CONFIGURED:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
    )
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jira_qa_crew.{name}")
