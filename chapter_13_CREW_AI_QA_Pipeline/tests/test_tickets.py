"""Ticket parsing, normalization, validation and deduplication."""

from __future__ import annotations

import pytest

from jira_qa_crew.exceptions import TicketInputError
from jira_qa_crew.tickets import parse_ticket_input


@pytest.mark.parametrize(
    "raw",
    [
        "QATEST-7,QATEST-8",
        "QATEST-7 QATEST-8",
        "QATEST-7\nQATEST-8",
        "QATEST-7; QATEST-8",
        "  QATEST-7 ,\n QATEST-8  ",
    ],
)
def test_every_separator_is_accepted(raw: str) -> None:
    assert parse_ticket_input(raw).valid == ["QATEST-7", "QATEST-8"]


def test_keys_are_upper_cased() -> None:
    assert parse_ticket_input("qatest-7").valid == ["QATEST-7"]


def test_duplicates_are_reported_once_and_dropped() -> None:
    result = parse_ticket_input("QATEST-7, qatest-7, QATEST-8")
    assert result.valid == ["QATEST-7", "QATEST-8"]
    assert result.duplicates == ["QATEST-7"]


def test_invalid_keys_are_separated_not_silently_dropped() -> None:
    result = parse_ticket_input("QATEST-7, not-a-key, 12345, QATEST")
    assert result.valid == ["QATEST-7"]
    assert set(result.invalid) == {"not-a-key", "12345", "QATEST"}


def test_ticket_count_limit_is_enforced() -> None:
    raw = ", ".join(f"QA-{i}" for i in range(1, 8))
    result = parse_ticket_input(raw, max_tickets=3)
    assert len(result.valid) == 3
    assert len(result.dropped_over_limit) == 4


def test_oversized_input_is_rejected() -> None:
    with pytest.raises(TicketInputError):
        parse_ticket_input("QATEST-7 " * 5000, max_chars=100)


def test_empty_input_produces_no_tickets() -> None:
    result = parse_ticket_input("   ")
    assert not result.has_valid


def test_custom_pattern_is_honoured() -> None:
    result = parse_ticket_input("AB-1, QATEST-7", pattern=r"^QATEST-\d+$")
    assert result.valid == ["QATEST-7"]
    assert result.invalid == ["AB-1"]
