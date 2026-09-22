"""Reusable Streamlit UI pieces: theme, header, input, configuration status."""

from __future__ import annotations

from html import escape

import streamlit as st

from ..config import AppConfig
from ..logging_utils import mask
from ..models import StageProgress, StageState
from ..tickets import TicketParseResult, parse_ticket_input

THEME_CSS = """
<style>
:root {
  --qa-blue: #1B4F9C;
  --qa-blue-dark: #12356B;
  --qa-blue-soft: #EAF1FB;
  --qa-border: #D3DEEE;
}
.qa-header {
  background: linear-gradient(135deg, var(--qa-blue-dark), var(--qa-blue));
  padding: 1.4rem 1.6rem;
  border-radius: 12px;
  color: #FFFFFF;
  margin-bottom: 1.2rem;
}
.qa-header h1 { margin: 0; font-size: 1.85rem; font-weight: 700; color: #FFFFFF; }
.qa-header p  { margin: .4rem 0 0; font-size: .98rem; opacity: .92; }
.qa-badge {
  display: inline-block; padding: .16rem .6rem; border-radius: 999px;
  font-size: .74rem; font-weight: 700; letter-spacing: .02em;
}
.qa-badge-mcp     { background: #DCEBFB; color: #12356B; }
.qa-badge-rest    { background: #E5E9F0; color: #2C3A4F; }
.qa-badge-fixture { background: #FFF1CC; color: #7A5600; }
.qa-badge-ready   { background: #D8F3E0; color: #14532D; }
.qa-badge-config  { background: #FFE8D6; color: #7C2D12; }
.qa-badge-failed  { background: #FBDCDC; color: #7F1D1D; }
.qa-stage {
  border: 1px solid var(--qa-border); border-left: 4px solid var(--qa-blue);
  border-radius: 8px; padding: .55rem .8rem; margin-bottom: .4rem;
  background: #FFFFFF;
}
.qa-stage-pending  { border-left-color: #B7C2D2; opacity: .72; }
.qa-stage-running  { border-left-color: #1B4F9C; background: var(--qa-blue-soft); }
.qa-stage-complete { border-left-color: #1B9C5B; }
.qa-stage-warning  { border-left-color: #D98A00; }
.qa-stage-failed   { border-left-color: #C0392B; }
.qa-stage-name { font-weight: 650; font-size: .92rem; }
.qa-stage-msg  { font-size: .8rem; color: #566274; }

/* Sidebar configuration: collapsed rows that open on click */
section[data-testid="stSidebar"] [data-testid="stExpander"] {
  border: 1px solid var(--qa-border);
  border-radius: 10px;
  margin-bottom: .4rem;
  background: #FFFFFF;
  overflow: hidden;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  font-size: .86rem;
  padding: .45rem .6rem;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
  background: var(--qa-blue-soft);
}
.qa-cfg-body { padding: .1rem 0 .2rem; }
.qa-cfg-row { display: flex; gap: .5rem; font-size: .76rem; line-height: 1.6; }
.qa-cfg-label { color: #6B7687; flex: 0 0 4.1rem; }
.qa-cfg-value {
  color: #1B2430; font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all; flex: 1 1 auto;
}
.qa-cfg-value.is-muted { color: #93A0B2; font-style: italic; }

/* Advanced settings tiles */
.qa-tile {
  border: 1px solid var(--qa-border);
  border-radius: 10px;
  padding: .55rem .7rem .6rem;
  background: #FFFFFF;
  margin-bottom: .5rem;
}
.qa-tile-label {
  font-size: .68rem; font-weight: 700; letter-spacing: .06em;
  text-transform: uppercase; color: #6B7687;
}
.qa-tile-value {
  font-size: 1.02rem; font-weight: 700; color: var(--qa-blue-dark);
  margin: .18rem 0 .22rem; word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.qa-tile-value.is-muted {
  color: #93A0B2; font-style: italic; font-size: .9rem; font-weight: 600;
}
.qa-tile-hint { font-size: .72rem; color: #7A8797; line-height: 1.45; }
.qa-group {
  font-size: .72rem; font-weight: 700; letter-spacing: .07em;
  text-transform: uppercase; color: var(--qa-blue);
  margin: .3rem 0 .45rem;
}
</style>
"""

_STAGE_CLASS = {
    StageState.PENDING: "qa-stage-pending",
    StageState.RUNNING: "qa-stage-running",
    StageState.COMPLETED: "qa-stage-complete",
    StageState.WARNING: "qa-stage-warning",
    StageState.FAILED: "qa-stage-failed",
}

_STAGE_ICON = {
    StageState.PENDING: "○",
    StageState.RUNNING: "◐",
    StageState.COMPLETED: "●",
    StageState.WARNING: "▲",
    StageState.FAILED: "✕",
}


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_header(app_name: str) -> None:
    st.markdown(
        f"""
        <div class="qa-header">
          <h1>{app_name}</h1>
          <p>Generate test plans, test cases, traceability, and Playwright automation directly from Jira.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Badges carry a human label and a hover explanation. The SCREAMING_CASE enum
# value stays in the manifest and the markdown, where it is machine-read; it is
# not what a person should have to decode on screen.
_SOURCE_BADGE = {
    "MCP": ("qa-badge-mcp", "Jira · MCP", "Ticket read through the Jira MCP server."),
    "REST": ("qa-badge-rest", "Jira · REST", "Ticket read from the Jira REST API."),
    "FIXTURE": (
        "qa-badge-fixture",
        "Demo fixture",
        "Ticket read from a local sample file, not from live Jira.",
    ),
}

_READINESS_BADGE = {
    "READY": (
        "qa-badge-ready",
        "Ready to run",
        "The generated tests have everything they need to execute.",
    ),
    "NEEDS_CONFIGURATION": (
        "qa-badge-config",
        "Needs setup",
        "The code compiles, but URLs, selectors or logins must be filled in "
        "before it can run.",
    ),
    "NOT_AUTOMATED": (
        "qa-badge-failed",
        "No automation",
        "No Playwright code was produced for this ticket.",
    ),
}


def _badge(value: str, table: dict[str, tuple[str, str, str]], fallback: str) -> str:
    css, label, hint = table.get(value, (fallback, value, ""))
    title = f' title="{escape(hint)}"' if hint else ""
    return f'<span class="qa-badge {css}"{title}>{escape(label)}</span>'


def source_badge(source: str) -> str:
    return _badge(source, _SOURCE_BADGE, "qa-badge-rest")


def readiness_badge(readiness: str) -> str:
    return _badge(readiness, _READINESS_BADGE, "qa-badge-config")


# Round status indicators. Red is reserved for "required and missing", so a
# warning colour never competes with a real blocker.
READY = "ready"
REQUIRED = "required"
OPTIONAL = "optional"

_STATUS = {
    READY: ("🟢", "Ready"),
    REQUIRED: ("🔴", "Required"),
    OPTIONAL: ("⚠️", "Not set"),
}


def _detail_rows(rows: list[tuple[str, str]]) -> str:
    """Label/value rows. Values are escaped, so a URL is never auto-linkified."""
    return "".join(
        f'<div class="qa-cfg-row"><span class="qa-cfg-label">{escape(name)}</span>'
        f'<span class="qa-cfg-value{"" if value else " is-muted"}">'
        f"{escape(value or 'not configured')}</span></div>"
        for name, value in rows
    )


def _short_host(url: str) -> str:
    """Strip the scheme so a long Jira URL stays readable in a narrow sidebar."""
    return url.replace("https://", "").replace("http://", "").rstrip("/")


def _subsystem(
    title: str, status: str, rows: list[tuple[str, str]], hint: str = ""
) -> None:
    """One collapsible subsystem: status in the header, detail on click."""
    icon, label = _STATUS[status]
    with st.expander(f"{icon}  **{title}** · {label}", expanded=False):
        st.markdown(
            f'<div class="qa-cfg-body">{_detail_rows(rows)}</div>',
            unsafe_allow_html=True,
        )
        if hint:
            st.caption(hint)


def render_config_status(config: AppConfig) -> None:
    """Show readiness without ever printing a secret."""
    with st.sidebar:
        st.subheader("Configuration")
        readiness = config.readiness()
        mode = config.jira_integration_mode

        # An LLM is always needed; Jira providers depend on the selected mode.
        llm_status = READY if readiness["llm"] else REQUIRED

        if readiness["jira_rest"]:
            rest_status = READY
        elif mode == "rest" or (mode == "auto" and not readiness["jira_mcp"]):
            rest_status = REQUIRED
        else:
            rest_status = OPTIONAL

        if readiness["jira_mcp"]:
            mcp_status = READY
        elif mode == "mcp":
            mcp_status = REQUIRED
        else:
            mcp_status = OPTIONAL

        if config.demo_mode:
            rest_status = mcp_status = OPTIONAL

        _subsystem(
            "LLM",
            llm_status,
            [
                ("Model", config.llm.model),
                ("Key", mask(config.llm.api_key) if config.llm.api_key else ""),
                ("Temp", str(config.llm.temperature)),
            ],
            hint="" if readiness["llm"] else "Set LLM_MODEL and LLM_API_KEY in .env",
        )
        _subsystem(
            "Jira REST",
            rest_status,
            [
                ("Site", _short_host(config.rest.url)),
                (
                    "Auth",
                    f"{config.rest.auth_mode} · {config.rest.email}"
                    if config.rest.email
                    else config.rest.auth_mode,
                ),
                (
                    "Token",
                    mask(config.rest.api_token or config.rest.bearer_token)
                    if (config.rest.api_token or config.rest.bearer_token)
                    else "",
                ),
            ],
        )
        _subsystem(
            "Jira MCP",
            mcp_status,
            [
                ("Transport", config.mcp.transport),
                ("Server", _short_host(config.mcp.url) or config.mcp.command),
                ("Tool", config.mcp.get_issue_tool or "auto-detect"),
            ],
            hint="Optional. REST already covers this run."
            if mcp_status == OPTIONAL
            else "",
        )

        mode_label = {
            "auto": "Auto — MCP, falling back to REST",
            "mcp": "MCP only",
            "rest": "REST only",
        }.get(mode, mode)
        st.caption(
            f"**Mode:** {mode_label}  \n"
            f"**Environment:** `{config.app_env}` · **Output:** `{config.output_dir}`"
        )

        if config.demo_mode:
            keys = demo_ticket_keys()
            offer = f" Try {', '.join(keys)}." if keys else ""
            st.warning(
                "DEMO MODE is on. Tickets are read from local sample files, not "
                f"from Jira, and every artifact is labelled FIXTURE.{offer}",
                icon="🧪",
            )

        problems = config.validate()
        if problems:
            st.error("\n\n".join(f"- {p}" for p in problems))


def tile(label: str, value: str, hint: str = "", muted: bool = False) -> str:
    css = " is-muted" if muted else ""
    return (
        f'<div class="qa-tile">'
        f'<div class="qa-tile-label">{escape(label)}</div>'
        f'<div class="qa-tile-value{css}">{escape(value)}</div>'
        f'<div class="qa-tile-hint">{escape(hint)}</div>'
        f"</div>"
    )


def render_tile_row(tiles: list[str]) -> None:
    for column, tile in zip(st.columns(len(tiles)), tiles, strict=True):
        column.markdown(tile, unsafe_allow_html=True)


def _render_advanced_settings(config: AppConfig) -> None:
    """Show effective settings as labelled tiles rather than a raw JSON dump."""
    ac_field = config.rest.acceptance_criteria_field

    st.markdown('<div class="qa-group">Pipeline</div>', unsafe_allow_html=True)
    render_tile_row(
        [
            tile(
                "Max tickets",
                str(config.pipeline.max_tickets),
                "Tickets beyond this are dropped from the run.",
            ),
            tile(
                "Ticket timeout",
                f"{config.pipeline.ticket_timeout_seconds}s",
                "A ticket exceeding this is abandoned and marked failed.",
            ),
            tile(
                "Retries",
                str(config.pipeline.max_retries),
                "Retry attempts for transient Jira failures.",
            ),
        ]
    )

    st.markdown('<div class="qa-group">Model</div>', unsafe_allow_html=True)
    render_tile_row(
        [
            tile(
                "Temperature",
                str(config.llm.temperature),
                "Low keeps analysis consistent rather than creative.",
            ),
            tile(
                "Max tokens",
                str(config.llm.max_tokens),
                "Output budget per agent. Raise if reports truncate.",
            ),
            tile(
                "Model",
                config.llm.model or "not set",
                "Configurable so provider renames cannot break the app.",
                muted=not config.llm.model,
            ),
        ]
    )

    st.markdown('<div class="qa-group">Jira</div>', unsafe_allow_html=True)
    render_tile_row(
        [
            tile(
                "Key pattern",
                config.jira_key_pattern,
                "Ticket IDs must match this to be accepted.",
            ),
            tile(
                "Acceptance criteria field",
                ac_field or "Not configured",
                "Custom field id holding acceptance criteria. When unset, they "
                "are read from the description.",
                muted=not ac_field,
            ),
            tile(
                "Comments",
                "Included" if config.rest.include_comments else "Excluded",
                f"Up to {config.rest.max_comments} comments are sent to the "
                "analyst." if config.rest.include_comments
                else "Comments are not sent to the analyst.",
                muted=not config.rest.include_comments,
            ),
        ]
    )

    if config.demo_mode:
        st.warning(
            "Demo mode is on: tickets come from local fixtures, not live Jira.",
            icon="🧪",
        )


def demo_ticket_keys() -> list[str]:
    """The sample tickets demo mode can serve, or [] when there are none."""
    try:
        from ..jira.fixture_provider import JiraFixtureProvider

        return JiraFixtureProvider().available_keys()
    except Exception:  # pragma: no cover - a missing fixture dir is not fatal
        return []


def render_ticket_input(config: AppConfig) -> tuple[str, str, bool, TicketParseResult]:
    """Render the input area and return (raw, mode, submitted, parsed)."""
    st.subheader("1 · Choose tickets")

    # In demo mode the placeholder must name tickets that actually exist. A
    # visitor to a public demo has no Jira to look them up in, and a suggested
    # key that resolves to nothing reads as the app being broken.
    demo_keys = demo_ticket_keys() if config.demo_mode else []
    placeholder = "\n".join(demo_keys) if demo_keys else "QATEST-7\nQATEST-8, VWO-50"

    col_input, col_mode = st.columns([3, 1])
    with col_input:
        raw = st.text_area(
            "Jira ticket IDs",
            key="ticket_input",
            height=120,
            placeholder=placeholder,
            help="Separate with commas, spaces, semicolons or new lines.",
        )
        if demo_keys:
            st.caption(f"Demo mode — available sample tickets: {', '.join(demo_keys)}")
    with col_mode:
        mode_label = st.selectbox(
            "Integration mode",
            options=["Auto (MCP → REST)", "MCP only", "REST only"],
            index=0,
            help="Which Jira provider to use. The choice is applied in code, "
            "not by the model.",
        )
        mode = {
            "Auto (MCP → REST)": "auto",
            "MCP only": "mcp",
            "REST only": "rest",
        }[mode_label]

    parsed = parse_ticket_input(
        raw or "",
        pattern=config.jira_key_pattern,
        max_tickets=config.pipeline.max_tickets,
    )

    if parsed.valid:
        st.caption(f"Will process: {', '.join(parsed.valid)}")
    if parsed.duplicates:
        st.info(f"Ignored duplicates: {', '.join(sorted(set(parsed.duplicates)))}")
    if parsed.invalid:
        st.warning(
            "Not valid Jira keys and will be skipped: "
            + ", ".join(parsed.invalid[:10])
        )
    if parsed.dropped_over_limit:
        st.warning(
            f"Over the {config.pipeline.max_tickets}-ticket limit, dropped: "
            + ", ".join(parsed.dropped_over_limit)
        )

    with st.expander("Advanced settings"):
        st.caption(
            "Read from the environment or secrets and shown for confirmation "
            "only. Change them in `.env`. Secrets are never displayed."
        )
        _render_advanced_settings(config)

    blocked = bool(config.validate())
    submitted = st.button(
        "Analyze & Generate QA Pack",
        type="primary",
        disabled=blocked or not parsed.valid,
        use_container_width=True,
    )
    if blocked:
        st.caption("Fix the configuration problems in the sidebar to enable the run.")

    return raw or "", mode, submitted, parsed


def render_stage(stage: StageProgress) -> None:
    css = _STAGE_CLASS.get(stage.state, "qa-stage-pending")
    icon = _STAGE_ICON.get(stage.state, "○")
    duration = (
        f" · {stage.duration_seconds}s" if stage.duration_seconds is not None else ""
    )
    st.markdown(
        f"""
        <div class="qa-stage {css}">
          <div class="qa-stage-name">{icon} {stage.name}{duration}</div>
          <div class="qa-stage-msg">{stage.message or stage.state.value.title()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
