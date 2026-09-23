"""A dummy Slack MCP server, for the reporting stage of 013.

Nothing here reaches Slack. Every call is recorded in memory and printed, so
you can watch the reporter agent compose and "post" a summary without a
workspace, a bot token, or the risk of an agent under development messaging a
real channel while you iterate on its prompt.

It is shaped like an MCP server on purpose - connect, a tool list, tools that
return strings - so that swapping in the real Slack MCP later is a change of
import and nothing else. It is *not* MCP: there is no protocol and no separate
process. See the note in 013 about local tools versus MCP.

To go live, replace SLACK_TOOLS with the real Slack MCP's tools. The agent
prompt does not need to change, because the tool names match.
"""

from __future__ import annotations

from datetime import datetime

from langchain.tools import tool

# Every simulated call, in order. 013 reads this to report how many were made.
_SENT: list[dict] = []

# A plausible channel list, so the agent can be asked to pick one.
_CHANNELS = [
    {"name": "#qa-automation", "purpose": "Automated test run results"},
    {"name": "#qa-alerts", "purpose": "Failing suites and flaky tests"},
    {"name": "#engineering", "purpose": "General engineering chat"},
    {"name": "#releases", "purpose": "Release announcements and sign-off"},
]


class _DummySlackMCP:
    """Stands in for a Slack MCP server without any of the wiring."""

    name = "slack-mcp (DUMMY)"

    @classmethod
    def connect(cls) -> str:
        """Announce the fake connection. Called by 013 before the reporter runs."""
        _SENT.clear()
        names = ", ".join(c["name"] for c in _CHANNELS)
        return (
            f"Connected to {cls.name}.\n"
            f"  transport : none - in-process stub, no network\n"
            f"  channels  : {names}\n"
            f"  NOTE      : messages are recorded and printed, never delivered."
        )


def sent_messages() -> list[dict]:
    """Every message the agent tried to post during this run."""
    return list(_SENT)


@tool
def slack_list_channels() -> str:
    """List the Slack channels available to post in, with what each is for.

    Call this if you are unsure which channel a message belongs in.
    """
    return "\n".join(f"{c['name']} - {c['purpose']}" for c in _CHANNELS)


@tool
def slack_post_message(channel: str, text: str) -> str:
    """Post one message to a Slack channel. Use Slack mrkdwn, not markdown.

    mrkdwn supports *bold*, _italic_, `code` and > quote. Tables and headings
    do not render, so use short lines instead.

    Post once per run: a summary, not a message per test case.
    """
    if not channel.startswith("#"):
        channel = f"#{channel}"

    known = {c["name"] for c in _CHANNELS}
    if channel not in known:
        # An error string, not an exception: the agent can read this and retry
        # with a real channel, where a raise would end the run.
        return (f"Error: no such channel {channel}. "
                f"Available: {', '.join(sorted(known))}")

    record = {
        "channel": channel,
        "text": text,
        "at": datetime.now().isoformat(timespec="seconds"),
    }
    _SENT.append(record)

    rule = "-" * 68
    print(f"\n{rule}\n[DUMMY SLACK] would post to {channel}:\n{rule}\n{text}\n{rule}")

    return (f"Message accepted for {channel} ({len(text)} chars). "
            f"NOT actually sent - this is a dummy server.")


SLACK_TOOLS = [slack_list_channels, slack_post_message]
