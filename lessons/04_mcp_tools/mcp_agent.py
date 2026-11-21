"""Lesson 04 - a Strands agent that uses tools from an MCP server.

Run:  uv run python lessons/04_mcp_tools/mcp_agent.py

The agent starts our support_mcp_server.py as a subprocess (stdio transport), discovers
its tools at runtime, and uses them next to a normal @tool function.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from mcp import StdioServerParameters, stdio_client
from strands import Agent, tool
from strands.models.model import Model
from strands.tools.mcp import MCPClient

from course_common import build_model, setup_logging, show_result

SERVER_SCRIPT = Path(__file__).with_name("support_mcp_server.py")


def support_desk_client() -> MCPClient:
    return MCPClient(
        # stdio: Strands launches the server process and talks over stdin/stdout.
        # Pin what you launch. In production prefer "uvx some-server==1.2.3" over "@latest".
        # (type: ignore - the mcp 2.x stream types are narrower than Strands' annotation)
        lambda: stdio_client(  # type: ignore[arg-type, return-value]
            StdioServerParameters(
                command=sys.executable,
                args=[str(SERVER_SCRIPT)],
                env={"PYTHONUNBUFFERED": "1"},  # only the env vars the server needs
            )
        ),
        # Tool names become "support_get_order_status": no clash with other servers.
        prefix="support",
        # Allow-list: the dangerous delete_ticket tool never reaches the model.
        # Filters match the server's ORIGINAL tool names (before the prefix).
        tool_filters={"allowed": ["get_order_status", re.compile(r"^list_")]},
        # Fail fast if the server does not start.
        startup_timeout=20,
    )


# For a remote server (Streamable HTTP) you only pass a URL (+ auth headers):
#   MCPClient(url="https://mcp.example.com/mcp", headers={"Authorization": f"Bearer {token}"})


@tool
def escalate_to_human(reason: str) -> str:
    """Hand the conversation to a human support agent.

    Args:
        reason: One sentence explaining why a human is needed.
    """
    return f"Escalated. A human will reply within 4 hours. Reason: {reason}"


def build_agent(model: Model | None = None, mcp_client: MCPClient | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        # An MCPClient sits in the tools list next to normal tools. The agent starts it
        # on first use and stops it when the agent is cleaned up (agent.cleanup()).
        tools=[mcp_client or support_desk_client(), escalate_to_human],
        system_prompt="You are a support agent. Use the support tools for order and ticket facts.",
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    try:
        print("tools:", agent.tool_names)
        result = agent("Where is order ORD-5521, and does customer C-1001 have open tickets?")
        print(result)
        show_result(result, agent.messages)
    finally:
        agent.cleanup()  # stops the MCP server subprocess


if __name__ == "__main__":
    main()
