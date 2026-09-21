"""Parse, normalize, deduplicate and validate Jira ticket input."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .exceptions import TicketInputError

_SEPARATORS = re.compile(r"[,\s;]+")

MAX_INPUT_CHARS = 10_000


@dataclass
class TicketParseResult:
    valid: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    dropped_over_limit: list[str] = field(default_factory=list)

    @property
    def has_valid(self) -> bool:
        return bool(self.valid)


def parse_ticket_input(
    raw: str,
    *,
    pattern: str = r"^[A-Z][A-Z0-9_]+-\d+$",
    max_tickets: int = 20,
    max_chars: int = MAX_INPUT_CHARS,
) -> TicketParseResult:
    """Split free-form ticket input into validated, deduplicated keys.

    Accepts commas, spaces, newlines and semicolons as separators. Keys are
    upper-cased before validation so ``qatest-7`` and ``QATEST-7`` are the same
    ticket.
    """
    if raw is None:
        raise TicketInputError("No ticket input supplied.")
    if len(raw) > max_chars:
        raise TicketInputError(
            f"Ticket input is too large ({len(raw)} characters, limit {max_chars})."
        )

    result = TicketParseResult()
    seen: set[str] = set()
    compiled = re.compile(pattern)

    for token in _SEPARATORS.split(raw.strip()):
        if not token:
            continue
        key = token.strip().upper()
        if not compiled.match(key):
            result.invalid.append(token.strip())
            continue
        if key in seen:
            result.duplicates.append(key)
            continue
        seen.add(key)
        if len(result.valid) >= max_tickets:
            result.dropped_over_limit.append(key)
            continue
        result.valid.append(key)

    return result
