"""FastMCP server exposing a VWO manual QA test-case export as tools, resources, and prompts."""

from __future__ import annotations

import csv
import logging
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Final

from fastmcp import FastMCP
from fastmcp.exceptions import PromptError, ResourceError, ToolError

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger: Final = logging.getLogger("vwo-testcases")

DEFAULT_CSV: Final[Path] = Path(__file__).resolve().parent / "resource" / "vwo_5000_test_cases.csv"
CSV_PATH: Final[Path] = Path(os.environ.get("VWO_CSV_PATH") or DEFAULT_CSV)

ID_COLUMN: Final[str] = "Issue Key"
MODULE_COLUMN: Final[str] = "Component"
SEARCH_COLUMNS: Final[tuple[str, ...]] = ("Summary", "Description", "Labels", "Expected Result")
ENUM_COLUMNS: Final[tuple[str, ...]] = (MODULE_COLUMN, "Priority", "Status", "Test Type")
GROUP_BY_ALIASES: Final[dict[str, str]] = {
    "module": MODULE_COLUMN,
    "component": MODULE_COLUMN,
    "priority": "Priority",
    "status": "Status",
    "type": "Test Type",
    "test type": "Test Type",
    "test_type": "Test Type",
}
MAX_LIMIT: Final[int] = 200


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read the CSV from disk and return its column names and rows."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        if not columns:
            raise ValueError("file has no header row")
        if ID_COLUMN not in columns:
            raise ValueError(f"file is missing the required {ID_COLUMN!r} column")
        rows = [{key: (value or "").strip() for key, value in row.items() if key} for row in reader]
    return list(columns), rows


def _load_dataset() -> tuple[list[str], list[dict[str, str]], str | None]:
    """Load the dataset once at startup, returning columns, rows, and any load error."""
    try:
        columns, rows = _read_csv(CSV_PATH)
    except (OSError, ValueError, csv.Error) as exc:
        message = f"Test-case dataset could not be loaded from {CSV_PATH}: {exc}"
        logger.error("%s", message)
        return [], [], message
    logger.info("loaded %d test cases from %s", len(rows), CSV_PATH)
    return columns, rows, None


COLUMNS, ROWS, LOAD_ERROR = _load_dataset()
BY_ID: Final[dict[str, dict[str, str]]] = {row[ID_COLUMN]: row for row in ROWS}
BY_MODULE: Final[defaultdict[str, list[dict[str, str]]]] = defaultdict(list)
for _row in ROWS:
    BY_MODULE[_row.get(MODULE_COLUMN, "").casefold()].append(_row)
MODULE_NAMES: Final[list[str]] = sorted({row.get(MODULE_COLUMN, "") for row in ROWS} - {""})


def _module_cases(name: str) -> list[dict[str, str]] | None:
    """Return the rows for a module name case-insensitively, or None when it is unknown."""
    return BY_MODULE.get(name.strip().casefold())


def _unknown_module(name: str) -> str:
    """Build a readable error message that lists every known module name."""
    return f"Unknown module {name!r}. Known modules: {', '.join(MODULE_NAMES)}."


def _unknown_test_case(test_id: str) -> str:
    """Build a readable error message for an unrecognised test-case ID."""
    example = next(iter(BY_ID), "VWO-1001")
    return f"Unknown test case {test_id!r}. Expected an issue key such as {example!r}."


mcp: Final = FastMCP(
    "vwo-testcases",
    instructions=(
        "Query a VWO manual QA test-case export. Tools search and aggregate the dataset, "
        "resources expose the schema and raw rows by URI, and prompts template review and "
        "regression-suite work. Test-case IDs are Jira-style issue keys such as VWO-1001; "
        "modules are Jira components such as Reports or Funnels."
    ),
)


@mcp.tool
def search_test_cases(query: str, module: str | None = None, limit: int = 20) -> list[dict[str, str]]:
    """Search test cases by free text, optionally restricted to a single module."""
    if LOAD_ERROR is not None:
        raise ToolError(LOAD_ERROR)
    needle = query.strip().casefold()
    if not needle:
        raise ToolError("query must not be empty.")
    if not 1 <= limit <= MAX_LIMIT:
        raise ToolError(f"limit must be between 1 and {MAX_LIMIT}, got {limit}.")
    if module is None:
        pool = ROWS
    else:
        cases = _module_cases(module)
        if cases is None:
            raise ToolError(_unknown_module(module))
        pool = cases
    matches = [
        row
        for row in pool
        if any(needle in row.get(column, "").casefold() for column in SEARCH_COLUMNS)
    ]
    if not matches:
        scope = f" in module {module!r}" if module else ""
        raise ToolError(f"No test cases match {query!r}{scope}.")
    return matches[:limit]


@mcp.tool
def get_test_case(test_id: str) -> dict[str, str]:
    """Return one complete test case by its issue key, for example VWO-1001."""
    if LOAD_ERROR is not None:
        raise ToolError(LOAD_ERROR)
    case = BY_ID.get(test_id.strip().upper())
    if case is None:
        raise ToolError(_unknown_test_case(test_id))
    return case


@mcp.tool
def test_case_stats(group_by: str = "module") -> dict[str, Any]:
    """Count test cases grouped by module, priority, status, or test type."""
    if LOAD_ERROR is not None:
        raise ToolError(LOAD_ERROR)
    column = GROUP_BY_ALIASES.get(group_by.strip().casefold())
    if column is None:
        valid = ", ".join(sorted(GROUP_BY_ALIASES))
        raise ToolError(f"Unknown group_by {group_by!r}. Valid values: {valid}.")
    counts = Counter(row.get(column, "") for row in ROWS)
    return {
        "group_by": column,
        "total": len(ROWS),
        "distinct": len(counts),
        "counts": dict(counts.most_common()),
    }


@mcp.resource("testcases://schema")
def schema() -> dict[str, Any]:
    """Column names, inferred types, and the allowed values of every enum column."""
    if LOAD_ERROR is not None:
        raise ResourceError(LOAD_ERROR)
    return {
        "source": str(CSV_PATH),
        "row_count": len(ROWS),
        "id_column": ID_COLUMN,
        "module_column": MODULE_COLUMN,
        "columns": [{"name": column, "type": "string"} for column in COLUMNS],
        "enums": {
            column: sorted({row.get(column, "") for row in ROWS} - {""})
            for column in ENUM_COLUMNS
            if column in COLUMNS
        },
    }


@mcp.resource("testcases://all")
def all_test_cases() -> dict[str, Any]:
    """The complete test-case dataset as JSON."""
    if LOAD_ERROR is not None:
        raise ResourceError(LOAD_ERROR)
    return {"count": len(ROWS), "cases": ROWS}


@mcp.resource("testcases://module/{name}")
def cases_by_module(name: str) -> dict[str, Any]:
    """All test cases belonging to a given module."""
    if LOAD_ERROR is not None:
        raise ResourceError(LOAD_ERROR)
    cases = _module_cases(name)
    if cases is None:
        raise ResourceError(_unknown_module(name))
    return {"module": cases[0].get(MODULE_COLUMN, name), "count": len(cases), "cases": cases}


@mcp.prompt
def review_test_case(test_id: str) -> str:
    """Prompt template that asks the model to critique one test case."""
    if LOAD_ERROR is not None:
        raise PromptError(LOAD_ERROR)
    case = BY_ID.get(test_id.strip().upper())
    if case is None:
        raise PromptError(_unknown_test_case(test_id))
    steps = "\n".join(
        f"  {step.strip()}" for step in case.get("Steps", "").split("|") if step.strip()
    )
    return (
        "Review the following VWO QA test case.\n\n"
        f"ID: {case.get(ID_COLUMN, '')}\n"
        f"Module: {case.get(MODULE_COLUMN, '')}\n"
        f"Summary: {case.get('Summary', '')}\n"
        f"Type: {case.get('Test Type', '')} | Priority: {case.get('Priority', '')} | "
        f"Status: {case.get('Status', '')}\n"
        f"Environment: {case.get('Browser', '')} on {case.get('Device', '')}\n\n"
        f"Preconditions: {case.get('Preconditions', '')}\n\n"
        f"Steps:\n{steps or '  (none recorded)'}\n\n"
        f"Expected result: {case.get('Expected Result', '')}\n\n"
        "Critique it on four axes: (1) coverage gaps and missing edge cases, (2) clarity and "
        "reproducibility of the steps, (3) whether the expected result is specific and verifiable, "
        "and (4) whether the recorded priority and test type are appropriate. "
        "Close with a rewritten version of the test case that resolves every issue you raise."
    )


@mcp.prompt
def generate_regression_suite(module: str) -> str:
    """Prompt template that builds a regression suite from one module's test cases."""
    if LOAD_ERROR is not None:
        raise PromptError(LOAD_ERROR)
    cases = _module_cases(module)
    if cases is None:
        raise PromptError(_unknown_module(module))
    catalogue = "\n".join(
        f"- {case.get(ID_COLUMN, '')} [{case.get('Priority', '')}/{case.get('Test Type', '')}/"
        f"{case.get('Status', '')}] {case.get('Summary', '')}"
        for case in cases
    )
    return (
        f"Assemble a regression suite for the {cases[0].get(MODULE_COLUMN, module)} module of VWO.\n\n"
        f"These are all {len(cases)} known test cases for the module, formatted as "
        "ID [Priority/Type/Status] Summary:\n\n"
        f"{catalogue}\n\n"
        "Select the subset that belongs in a regression suite, ordered by execution priority. "
        "Exclude Deprecated cases and justify every inclusion in one line. Group the result by "
        "test type, flag any coverage gap the existing cases do not address, and estimate the "
        "total execution time assuming five minutes per manual case."
    )


if __name__ == "__main__":
    mcp.run()
