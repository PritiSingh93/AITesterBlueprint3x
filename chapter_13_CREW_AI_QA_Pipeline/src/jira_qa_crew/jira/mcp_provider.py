"""Jira MCP provider (primary path).

A contained MCP client is used rather than CrewAI's ``mcps`` DSL. The DSL hands
tool selection to the LLM, but the MCP-to-REST fallback in
:class:`~.gateway.JiraGateway` has to be a deterministic application decision,
which requires owning the connection lifecycle and seeing failures directly.

Each fetch opens and closes its own session. That costs a process spawn per
ticket but keeps Streamlit reruns from leaking subprocesses.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import re
from contextlib import asynccontextmanager
from typing import Any

from ..config import JiraMCPConfig
from ..exceptions import (
    JiraNotFoundError,
    JiraProviderUnavailableError,
    JiraResponseError,
    JiraTransientError,
)
from ..logging_utils import get_logger, redact
from ..models import JiraIssue, ProviderSource
from .adf import extract_text
from .base import HealthStatus, JiraProvider

logger = get_logger("jira.mcp")

# A tool whose name matches any of these is never called, whatever the
# allowlist says. Defence in depth against a server exposing write tools.
_MUTATING = re.compile(
    r"(create|update|delete|remove|add|edit|set_|assign|transition|move|"
    r"archive|upload|write|comment_add|link_issue|batch_)",
    re.IGNORECASE,
)

_GET_ISSUE_HINTS = ("get_issue", "getissue", "issue_get", "read_issue", "fetch_issue")


def _is_read_only(tool_name: str) -> bool:
    return not _MUTATING.search(tool_name or "")


def _run_async(coro_factory: Any, timeout: int) -> Any:
    """Run a coroutine on a private event loop in a worker thread."""

    def runner() -> Any:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                asyncio.wait_for(coro_factory(), timeout=timeout)
            )
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                asyncio.set_event_loop(None)
                loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(runner)
        # Give the thread a little longer than the inner asyncio timeout so the
        # inner TimeoutError surfaces with its better message.
        return future.result(timeout=timeout + 15)


class JiraMCPProvider(JiraProvider):
    name = "MCP"

    def __init__(self, config: JiraMCPConfig) -> None:
        self._config = config

    @property
    def configured(self) -> bool:
        return self._config.configured

    # -- session -----------------------------------------------------------

    @asynccontextmanager
    async def _session(self):
        from mcp import ClientSession, StdioServerParameters

        transport = self._config.transport
        if transport == "stdio":
            from mcp.client.stdio import stdio_client

            params = StdioServerParameters(
                command=self._config.command,
                args=list(self._config.args),
                env=dict(self._config.env),
            )
            async with (
                stdio_client(params) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                yield session
        elif transport in {"streamable_http", "http"}:
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(
                self._config.url, headers=dict(self._config.headers)
            ) as (read, write, _), ClientSession(read, write) as session:
                await session.initialize()
                yield session
        elif transport == "sse":
            from mcp.client.sse import sse_client

            async with sse_client(
                self._config.url, headers=dict(self._config.headers)
            ) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                yield session
        else:
            raise JiraProviderUnavailableError(
                f"Unsupported JIRA_MCP_TRANSPORT {transport!r}. "
                "Use stdio, streamable_http or sse."
            )

    def _resolve_tool_name(self, available: list[str]) -> str:
        """Pick the issue-fetch tool. Never assume a server's naming."""
        configured = self._config.get_issue_tool
        if configured:
            if configured not in available:
                raise JiraResponseError(
                    f"MCP server does not expose {configured!r}. "
                    f"Available tools: {', '.join(sorted(available)) or 'none'}"
                )
            return configured

        allowed = [t for t in available if t in self._config.allowed_tools]
        for candidate in allowed:
            if _is_read_only(candidate):
                return candidate

        for tool in available:
            lowered = tool.lower()
            if any(h in lowered for h in _GET_ISSUE_HINTS) and _is_read_only(tool):
                return tool

        raise JiraResponseError(
            "Could not find a read-only get-issue tool on the MCP server. "
            "Set JIRA_MCP_GET_ISSUE_TOOL explicitly. "
            f"Available: {', '.join(sorted(available)) or 'none'}"
        )

    # -- public API --------------------------------------------------------

    def fetch_issue(self, issue_key: str) -> JiraIssue:
        if not self.configured:
            raise JiraProviderUnavailableError(
                "Jira MCP is not configured (need JIRA_MCP_COMMAND or JIRA_MCP_URL)."
            )

        async def work() -> str:
            async with self._session() as session:
                listed = await session.list_tools()
                names = [t.name for t in listed.tools]
                tool_name = self._resolve_tool_name(names)
                if not _is_read_only(tool_name):
                    raise JiraProviderUnavailableError(
                        f"Refusing to call MCP tool {tool_name!r}: it looks mutating."
                    )
                arguments = {self._config.issue_key_argument: issue_key}
                result = await session.call_tool(tool_name, arguments)
                if getattr(result, "isError", False):
                    raise JiraResponseError(
                        f"MCP tool {tool_name} reported an error for {issue_key}."
                    )
                return _content_to_text(result)

        try:
            raw = _run_async(work, self._config.timeout_seconds)
        except TimeoutError as exc:
            raise JiraTransientError(
                f"MCP did not respond within {self._config.timeout_seconds}s "
                f"for {issue_key}."
            ) from exc
        except concurrent.futures.TimeoutError as exc:
            raise JiraTransientError(
                f"MCP client thread did not finish for {issue_key}."
            ) from exc
        except (JiraResponseError, JiraProviderUnavailableError):
            raise
        except Exception as exc:  # transport/process failures
            raise JiraTransientError(
                f"MCP transport failed for {issue_key}: {redact(exc)}"
            ) from exc

        issue = self._parse(issue_key, raw)
        logger.info("Fetched %s via MCP", issue_key)
        return issue

    def health_check(self) -> HealthStatus:
        if not self.configured:
            return HealthStatus(False, "MCP not configured")

        async def work() -> list[str]:
            async with self._session() as session:
                listed = await session.list_tools()
                return [t.name for t in listed.tools]

        try:
            names = _run_async(work, self._config.timeout_seconds)
        except Exception as exc:
            return HealthStatus(False, f"MCP unreachable: {redact(exc)}")
        return HealthStatus(True, f"MCP reachable, {len(names)} tools")

    # -- parsing -----------------------------------------------------------

    def _parse(self, issue_key: str, raw: str) -> JiraIssue:
        if not raw or not raw.strip():
            raise JiraResponseError(f"MCP returned an empty payload for {issue_key}.")

        data = _loads(raw)
        if data is None:
            # Some servers return prose. Keep it as the description rather than
            # discarding a usable ticket body.
            return JiraIssue(
                key=issue_key,
                summary=f"{issue_key} (unstructured MCP response)",
                description=raw.strip(),
                source=ProviderSource.MCP,
            )

        if isinstance(data, list):
            data = next((d for d in data if isinstance(d, dict)), None)
            if data is None:
                raise JiraResponseError(
                    f"MCP returned a list with no object for {issue_key}."
                )

        lowered = str(data.get("error") or data.get("message") or "").lower()
        if "does not exist" in lowered or "not found" in lowered:
            raise JiraNotFoundError(f"{issue_key} was not found via MCP.")

        fields = data.get("fields") if isinstance(data.get("fields"), dict) else {}
        merged: dict[str, Any] = {**fields, **data}

        key = str(merged.get("key") or issue_key)
        return JiraIssue(
            key=key,
            summary=str(merged.get("summary") or ""),
            description=extract_text(merged.get("description")),
            issue_type=_name_of(merged.get("issuetype") or merged.get("issue_type")),
            status=_name_of(merged.get("status")),
            priority=_name_of(merged.get("priority"), default="Not set"),
            labels=_str_list(merged.get("labels")),
            components=_str_list(merged.get("components")),
            parent=_key_of(merged.get("parent")),
            subtasks=_str_list(merged.get("subtasks"), field="key"),
            linked_issues=_str_list(
                merged.get("issuelinks") or merged.get("linked_issues"), field="key"
            ),
            acceptance_criteria_raw=extract_text(
                merged.get("acceptance_criteria")
                or merged.get(self._config.issue_key_argument + "_acceptance_criteria")
            ),
            comments=_comment_list(merged.get("comments") or merged.get("comment")),
            url=str(merged.get("url") or merged.get("self") or ""),
            source=ProviderSource.MCP,
        )


# -- helpers ---------------------------------------------------------------


def _content_to_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            parts.append(str(text))
    if not parts:
        structured = getattr(result, "structuredContent", None)
        if structured:
            return json.dumps(structured)
    return "\n".join(parts)


def _loads(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _name_of(value: Any, default: str = "Unknown") -> str:
    if isinstance(value, dict):
        return str(value.get("name") or default)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _key_of(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("key")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _str_list(value: Any, field: str = "name") -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    out: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for side in ("inwardIssue", "outwardIssue"):
                    nested = item.get(side)
                    if isinstance(nested, dict) and nested.get("key"):
                        out.append(str(nested["key"]))
                        break
                else:
                    found = item.get(field) or item.get("key") or item.get("name")
                    if found:
                        out.append(str(found))
    return out


def _comment_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        value = value.get("comments")
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for entry in value:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict):
            author = entry.get("author")
            author_name = (
                author.get("displayName") if isinstance(author, dict) else author
            ) or "Unknown"
            body = extract_text(entry.get("body") or entry.get("text"))
            if body:
                out.append(f"{author_name}: {body}")
    return out
