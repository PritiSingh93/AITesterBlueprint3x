"""Guard against credentials reaching a committed file.

`.env` is gitignored, but `.env.example` is deliberately committed as a
template. Filling the template in with live values is an easy mistake and
publishes the secret on the next push, so it is checked here instead of relying
on someone noticing in review.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Value shapes that are recognisably real credentials rather than placeholders.
_REAL_SECRET = re.compile(
    r"(ATATT[A-Za-z0-9_\-=.]{20,}"
    r"|gsk_[A-Za-z0-9]{30,}"
    r"|sk-[A-Za-z0-9\-_]{30,}"
    r"|xox[baprs]-[A-Za-z0-9-]{20,})"
)

# Files that ship with the repository and must never carry a live value.
COMMITTED_FILES = [
    ".env.example",
    ".streamlit/secrets.toml.example",
    "README.md",
    "docker-compose.yml",
    "Dockerfile",
]


@pytest.mark.parametrize("relative", COMMITTED_FILES)
def test_committed_file_has_no_live_credential(relative: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        pytest.skip(f"{relative} is not present")
    found = _REAL_SECRET.findall(path.read_text(encoding="utf-8"))
    assert not found, (
        f"{relative} contains what looks like a live credential "
        f"({found[0][:8]}...). Replace it with an empty placeholder: this file "
        "is committed."
    )


def test_env_example_ships_empty_credential_fields() -> None:
    """The template documents the keys; it never carries their values."""
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    for key in ("LLM_API_KEY", "JIRA_API_TOKEN", "JIRA_BEARER_TOKEN", "JIRA_EMAIL"):
        matching = [x for x in lines if x.startswith(f"{key}=")]
        assert matching, f"{key} should be documented in .env.example"
        assert matching[0] == f"{key}=", f"{key} must ship empty, got {matching[0][:40]}"


def test_source_tree_has_no_hard_coded_credential() -> None:
    offenders: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        if _REAL_SECRET.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"Credentials found in source: {offenders}"


def test_fixtures_have_no_credentials() -> None:
    offenders: list[str] = []
    for path in (ROOT / "fixtures").rglob("*.json"):
        if _REAL_SECRET.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"Credentials found in fixtures: {offenders}"
