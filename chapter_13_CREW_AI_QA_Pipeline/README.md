# Jira QA Crew

Generate test plans, test cases, traceability, and Playwright automation directly from Jira.

Enter one or more Jira ticket IDs. Four CrewAI agents run in sequence per ticket and produce a
reviewable QA pack: a requirements analysis, a 12-section test plan, detailed test cases, a
requirements-to-tests traceability matrix, and Playwright TypeScript automation — downloadable as
Markdown, CSV, TypeScript, JSON, or a single ZIP.

This is a generation and review tool. It never writes to Jira, never transitions issues, and never
executes Playwright against your environments.

---

## Contents

- [Architecture](#architecture)
- [The pipeline](#the-pipeline)
- [Repository structure](#repository-structure)
- [Local installation](#local-installation)
- [Configuration](#configuration)
- [Jira MCP setup](#jira-mcp-setup)
- [Jira REST fallback setup](#jira-rest-fallback-setup)
- [Running the app](#running-the-app)
- [Demo mode](#demo-mode)
- [Tests](#tests)
- [Deployment](#deployment)
- [Security notes](#security-notes)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

---

## Architecture

Three layers, deliberately separated:

```
Streamlit UI  (src/jira_qa_crew/ui, app.py)
      │  only presentation and session state
      ▼
Services      (src/jira_qa_crew/services)
      │  pipeline, validation, traceability, rendering, artifacts
      ▼
Integration   (src/jira_qa_crew/jira, crew, tools)
         gateway + providers, CrewAI agents and tasks
```

Four decisions shape everything else:

**1. Provider selection is application logic, not an LLM decision.**
CrewAI's `mcps` DSL attaches MCP servers directly to an agent and lets the model choose tools. That
cannot express "try MCP, and if it fails use REST," because the fallback would become a model
judgment call. `JiraGateway` owns that decision in Python and exposes a single read-only
`fetch_jira_issue` tool to the analyst instead.

**2. The tool schema is deliberately narrow.**
MCP servers commonly mark every optional parameter of their get-issue tool as required. Strict
providers then reject the model's call with a 400 before any work happens. `FetchJiraIssueTool`
exposes only `issue_key`, which the model can always satisfy; the optional parameters are left to
the MCP server's own defaults.

**3. Jira facts never come from an LLM.**
`JiraIssue` is read from a provider and carries the key, summary, status, priority, labels and
components. Agents produce only *analysis*. The two are merged in Python by `RequirementAnalysis`,
so a hallucinated ticket field cannot reach an artifact.

**4. Artifacts are rendered by deterministic Python.**
Agents return validated Pydantic objects, not Markdown. `services/renderers.py` turns those objects
into files, so the same validated object always produces byte-identical output, and the model's
prose is never the source of truth.

Coverage and traceability are likewise computed in Python. A model grading its own coverage is not
evidence.

---

## The pipeline

```
Jira IDs
   ↓  parsed, upper-cased, deduplicated, validated against a configurable key pattern
JiraGateway        →  MCP, falling back to REST (mode: auto | mcp | rest)
   ↓  deterministic fetch happens BEFORE any tokens are spent
Jira Analyst       →  requirements, acceptance criteria, risks, gaps   (AnalysisPayload)
   ↓
Test Plan Writer   →  12 sections + traceable scenarios                (TestPlan)
   ↓
Test Case Writer   →  8-15 traceable, executable cases                 (TestCaseSuite)
   ↓
Playwright Coder   →  TypeScript specs + mappings + readiness          (PlaywrightBundle)
   ↓
Validation → Traceability → Artifacts → Streamlit results and downloads
```

Each stage returns a validated Pydantic object via `output_pydantic`, and later tasks receive
earlier outputs as explicit `context`. Deterministic validation runs after every stage.

### Agent responsibilities

| Agent | Produces | Refuses to |
| --- | --- | --- |
| **Jira Analyst** | `REQ-*` / `AC-*` with evidence quotes and an EXPLICIT / INFERRED / ASSUMPTION classification | Invent acceptance criteria, or fill gaps it should record under `missing_information` |
| **Test Plan Writer** | 12 sections, scenarios traceable to `REQ-*` / `AC-*` | Emit generic filler that would read identically for another ticket |
| **Test Case Writer** | Traceable cases with numbered steps, data, priority, automation candidacy | Force irrelevant categories onto a ticket that does not support them |
| **Playwright Coder** | TypeScript specs, traceability comments, readiness status | Invent selectors, routes or credentials, or call a scaffold execution-ready |

### Per-ticket isolation

Every ticket gets a fresh crew, fresh agents and a fresh tool instance, so requirements cannot leak
between unrelated tickets in one run. Tickets continue on error: one failure never costs the run.
A run is successful when at least one ticket produced usable output, and a ticket is never marked
successful when required output is missing.

---

## Repository structure

```
app.py                          Streamlit entry point
src/jira_qa_crew/
├── config.py                   env + st.secrets, startup validation
├── models.py                   Pydantic domain models
├── exceptions.py               typed exception hierarchy
├── security.py                 path sanitization, untrusted-content fencing
├── logging_utils.py            structured logging with secret redaction
├── tickets.py                  ticket parsing, normalization, deduplication
├── jira/
│   ├── base.py                 JiraProvider interface
│   ├── gateway.py              deterministic MCP → REST fallback
│   ├── mcp_provider.py         contained MCP client (stdio / http / sse)
│   ├── rest_provider.py        Jira Cloud REST v3
│   ├── fixture_provider.py     demo mode only, never an automatic fallback
│   └── adf.py                  Atlassian Document Format → text
├── tools/jira_tool.py          read-only FetchJiraIssueTool
├── crew/                       agents, tasks, per-ticket factory, callbacks
├── prompts/                    agents.yaml, tasks.yaml
├── services/                   pipeline, validation, traceability, renderers, artifacts
└── ui/                         state, components, results
tests/                          217 tests
fixtures/jira/                  demo tickets
outputs/                        generated artifacts (gitignored)
```

### Artifact layout

```
outputs/<run_id>/
├── run_summary.md
├── manifest.json
└── <TICKET-KEY>/
    ├── requirements_analysis.md / .json
    ├── test_plan.md
    ├── test_cases.md / .csv
    ├── traceability_matrix.md / .csv
    ├── playwright_tests.md
    ├── manifest.json
    └── playwright/tests/<ticket>.spec.ts
```

---

## Local installation

Requires **Python 3.11 or newer**.

```bash
cd chapter_13_CREW_AI_QA_Pipeline

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
pip install pytest ruff       # for the test suite
```

---

## Configuration

Copy `.env.example` to `.env` and fill it in. Nothing is hard-coded, and the model id is
configurable on purpose: provider naming changes, and a wrong literal is a silent production
failure.

```dotenv
LLM_MODEL=openai/openai/gpt-oss-120b
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_TEMPERATURE=0.1

JIRA_INTEGRATION_MODE=auto        # auto | mcp | rest
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your-token
```

The sidebar shows readiness for each subsystem and lists actionable problems. Secrets are shown
only masked (`ATAT…9f2c`), never in full.

Configuration is read from environment variables first, then `st.secrets`. For Streamlit Community
Cloud, copy `.streamlit/secrets.toml.example` into the app's Secrets box.

---

## Jira MCP setup

MCP is the primary provider. Tool names differ between MCP servers, so the integration never
assumes one — set `JIRA_MCP_GET_ISSUE_TOOL` explicitly, or leave it empty to auto-detect from
`JIRA_MCP_ALLOWED_TOOLS`.

**stdio** (a local server subprocess, e.g. `mcp-atlassian` via `uvx`):

```dotenv
JIRA_MCP_TRANSPORT=stdio
JIRA_MCP_COMMAND=uvx
JIRA_MCP_ARGS_JSON=["mcp-atlassian"]
JIRA_MCP_GET_ISSUE_TOOL=jira_get_issue
```

Credentials are passed into the subprocess environment, defaulting to your `JIRA_URL`,
`JIRA_EMAIL` and `JIRA_API_TOKEN`.

**streamable HTTP** (a remote server):

```dotenv
JIRA_MCP_TRANSPORT=streamable_http
JIRA_MCP_URL=https://mcp.example.com/jira
JIRA_MCP_HEADERS_JSON={"Authorization":"Bearer ..."}
```

`sse` is also supported. Only read-only tools are ever called: a tool whose name matches a mutating
pattern (`create`, `update`, `delete`, `transition`, `add`, …) is refused even if it appears in the
allowlist.

---

## Jira REST fallback setup

Used automatically in `auto` mode when MCP fails, or exclusively in `rest` mode.

```dotenv
JIRA_URL=https://your-domain.atlassian.net
JIRA_AUTH_MODE=basic              # basic (email + API token) or bearer
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your-token
JIRA_API_VERSION=3
JIRA_ACCEPTANCE_CRITERIA_FIELD=customfield_10001
JIRA_INCLUDE_COMMENTS=false
```

Create an API token at **Jira → profile → Manage account → Security → API tokens**.

It calls `/rest/api/3/issue/{key}`, walks the full ADF tree (so nothing past the first paragraph is
lost), and maps HTTP failures to typed errors: 401 auth, 403 permission, 404 not found, 429 rate
limit, 5xx and timeouts transient with bounded exponential-backoff retries.

`JIRA_ACCEPTANCE_CRITERIA_FIELD` is the custom field id holding acceptance criteria; it varies per
Jira site, so it is configurable rather than guessed.

---

## Running the app

```bash
streamlit run app.py
```

Then open http://localhost:8501.

1. Enter ticket IDs separated by commas, spaces, semicolons or new lines.
2. Pick an integration mode (Auto / MCP only / REST only).
3. Press **Analyze & Generate QA Pack**.
4. Review each ticket's six tabs and download the artifacts.

---

## Demo mode

Explores the app with no Jira and no live credentials, using `fixtures/jira/*.json`:

```dotenv
DEMO_MODE=true
```

Demo mode must be enabled explicitly, is labelled in the UI, and every artifact is tagged
`FIXTURE`. **It is never an automatic fallback for a failed live integration** — a test asserts
exactly that, because silently substituting fake data for a broken Jira connection is how a team
ships a QA pack for a ticket nobody read.

You still need an LLM configured; demo mode replaces Jira, not the agents.

---

## Tests

```bash
pytest -m "not integration"                  # 217 tests, no credentials needed
ruff check src tests app.py
pytest -m integration                        # opt-in, needs real credentials
```

The default suite never calls a real Jira instance or a paid LLM. Coverage includes ticket parsing,
ADF conversion, every gateway path (MCP success, MCP→REST fallback, REST-only, both-failed,
no-silent-demo-fallback), the REST error taxonomy, MCP tool resolution and parsing, structured
output validation and repair, duplicate-ID and traceability checks, rendering, artifact paths and
ZIP generation, secret redaction, path traversal, partial multi-ticket success, and the Streamlit UI
via `streamlit.testing.v1.AppTest`.

Opt-in integration tests need `JIRA_URL`, `JIRA_API_TOKEN` and `INTEGRATION_TICKET_KEY` (plus
`LLM_API_KEY` for the full-pipeline one) and are skipped otherwise.

---

## Deployment

### Streamlit Community Cloud

1. Push the repository to GitHub.
2. Create an app pointing at `chapter_13_CREW_AI_QA_Pipeline/app.py`.
3. Paste `.streamlit/secrets.toml.example` contents into **Secrets** and fill them in.
4. Set `JIRA_INTEGRATION_MODE=rest`.

Community Cloud cannot spawn a local stdio MCP subprocess. Use `rest` mode there, or point
`JIRA_MCP_TRANSPORT=streamable_http` at a remote MCP server.

### Docker

```bash
docker compose up --build       # http://localhost:8501
```

The image runs as a non-root user, reads configuration from `.env`, and mounts `./outputs` so
generated artifacts survive the container.

---

## Security notes

- Secrets come from environment variables or `st.secrets`, never from UI text fields, and are
  displayed only masked.
- Every log record and user-visible error passes through `redact()`, which scrubs configured secret
  values *and* recognisable token shapes (`ATATT…`, `gsk_…`, `sk-…`, `Bearer …`) — so a token pasted
  into a ticket description cannot reach a log just because it was never an environment variable.
- Jira access is read-only. Mutating MCP tool names are refused regardless of the allowlist.
- Jira content is treated as untrusted data. It is fenced in explicit delimiters, the guard
  instructs agents to ignore embedded instructions, and content cannot forge a closing delimiter to
  break out of the block.
- The Jira tool answers only for tickets in the current run, so "now read ADMIN-1" in a ticket
  description is refused rather than obeyed.
- Every path segment — ticket keys and model-proposed filenames alike — is sanitized, and writes are
  verified to resolve inside the run directory.
- Input size, ticket count, network timeouts and retries are bounded. No `eval`, no `exec`, no shell
  execution from Jira content, no unsafe deserialization, and Playwright is never executed by the
  server.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Run button disabled | Configuration problems in the sidebar, or no valid ticket key entered. |
| `Could not fetch X from any provider` | The message lists each provider's reason. Check credentials, the ticket key, and project permissions. |
| `parameters for tool ... did not match schema` | An MCP server marked optional parameters as required. This app avoids it by exposing only `issue_key`; if you see it elsewhere, narrow the tool schema the same way. |
| `Could not find a read-only get-issue tool` | Set `JIRA_MCP_GET_ISSUE_TOOL` to the exact tool name your server exposes. |
| Tickets fall back to REST every time | Check MCP health in the sidebar. In stdio mode, confirm the command runs standalone. |
| `did not return valid ... output` | The model returned unparseable JSON twice over. Lower `LLM_TEMPERATURE`, or use a model with stronger structured output. |
| Stage output truncated | Raise `LLM_MAX_TOKENS`, or use a model with a larger request budget. Prompts already cap section lengths. |
| Readiness always `NEEDS_CONFIGURATION` | Expected when the ticket does not supply real selectors, routes or credentials. The agent is instructed not to invent them. |

---

## Limitations

- **Generated Playwright code is a starting point, not a verified suite.** When a ticket lacks real
  selectors and routes, the agent emits a compilable scaffold marked `NEEDS_CONFIGURATION`. A human
  supplies the specifics. Readiness is downgraded automatically if placeholders remain.
- **Output quality tracks ticket quality.** A one-line ticket yields a thin analysis. Gaps are
  reported under `missing_information` rather than filled in.
- **A per-ticket timeout abandons the run but cannot kill the worker thread.** Python offers no safe
  forced termination; the ticket is reported as failed and never as successful.
- **Token usage is not reported.** Nothing in the UI claims a cost figure it cannot substantiate.
- **Live Jira, MCP and LLM paths need real credentials** and are exercised only by the opt-in
  integration tests.
