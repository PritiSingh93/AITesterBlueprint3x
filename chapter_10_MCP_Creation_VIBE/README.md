# vwo-testcases MCP server

An MCP server over a 5,000-row VWO manual QA test-case export. It exists to make the
**tools vs. resources vs. prompts** distinction concrete in one file.

- **Tools** — model-invoked actions. The LLM decides to call them.
- **Resources** — application-controlled context, addressed by URI. The client reads them.
- **Prompts** — user-invoked templates. The user picks them from a menu.

Built on FastMCP 3.4.6, Python 3.11+, stdio transport.

## Layout

```
chapter_10_MCP_Creation_VIBE/
├── server.py                        # the server: 3 tools, 3 resources, 2 prompts
├── pyproject.toml                   # pinned dependencies
├── README.md
└── resource/
    └── vwo_5000_test_cases.csv      # dataset, loaded once at startup
```

## Dataset

14 columns, 5,000 rows, all `Issue Type = Test`.

| Column | Role |
| --- | --- |
| `Issue Key` | test ID (`VWO-1001` … `VWO-6000`) |
| `Component` | module — 17 values (Reports, Funnels, SmartCode, …) |
| `Priority` | Highest, High, Medium, Low |
| `Status` | Ready, Automated, Draft, Deprecated |
| `Test Type` | Functional, Negative, UI/UX, API, Boundary, Regression, Security, Accessibility, Performance |
| `Summary`, `Description`, `Labels`, `Preconditions`, `Steps`, `Expected Result`, `Browser`, `Device` | test body |

`Steps` is a single string with steps separated by ` | `.

## Install

```bash
cd chapter_10_MCP_Creation_VIBE
uv sync
```

## Run

```bash
uv run python server.py
```

The server speaks stdio. Started by hand it waits on stdin — that is correct. Real
clients spawn it as a subprocess. All logging goes to **stderr**; stdout carries only
JSON-RPC.

## Inspect

```bash
uv run fastmcp dev inspector server.py
```

Opens the MCP Inspector in a browser. Note the `inspector` subcommand — FastMCP 3.x
changed this from the 2.x `fastmcp dev <file>` form.

## Register with Claude Desktop

Config file:

- Windows — `%APPDATA%\Claude\claude_desktop_config.json`
- macOS — `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "vwo-testcases": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\LENOVO\\Documents\\AITesterBlueprint3x\\chapter_10_MCP_Creation_VIBE",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

Replace the directory with your own absolute path. If Claude Desktop reports
`command not found`, use the absolute path to `uv` (`where.exe uv`). Restart Claude
Desktop after editing.

## Primitives

### Tools

| Tool | Signature | Notes |
| --- | --- | --- |
| `search_test_cases` | `(query: str, module: str \| None = None, limit: int = 20)` | Substring match over Summary, Description, Labels, Expected Result. `limit` 1–200. |
| `get_test_case` | `(test_id: str)` | One case by issue key. Case- and whitespace-tolerant. |
| `test_case_stats` | `(group_by: str = "module")` | Accepts `module`, `priority`, `status`, `type` (plus `component`, `test_type`, `test type`). |

### Resources

| URI | Returns |
| --- | --- |
| `testcases://schema` | Column names, types, row count, and every enum column's allowed values. |
| `testcases://all` | `{count, cases}` — the full dataset. |
| `testcases://module/{name}` | `{module, count, cases}` — templated, case-insensitive. |

### Prompts

| Prompt | Purpose |
| --- | --- |
| `review_test_case(test_id)` | Critique one case on coverage, clarity, verifiability, and priority, then rewrite it. |
| `generate_regression_suite(module)` | Select and order a regression suite from that module's cases, with gaps and time estimate. |

## Dataset path

Resolved relative to `server.py` as `./resource/vwo_5000_test_cases.csv`. Override with
an environment variable:

```bash
# PowerShell
$env:VWO_CSV_PATH = "D:\exports\other_cases.csv"; uv run python server.py
```

If the CSV is missing or malformed the server still starts and every primitive returns a
readable error naming the path. It does not crash.

## Verify

In the Inspector:

1. **Tools** → `test_case_stats` with `group_by=module` → 5,000 total across 17 modules.
2. **Tools** → `get_test_case` with `test_id=VWO-9999` → readable error, no stack trace.
3. **Resources** → `testcases://schema` → 14 columns and the enum lists.
4. **Resources** → template `testcases://module/{name}` with `name=Funnels` → 278 cases.
5. **Prompts** → `review_test_case` with `test_id=VWO-1003` → a filled-in review prompt.
