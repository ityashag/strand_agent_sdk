"""Lesson 04 - a small MCP server that exposes support-desk tools.

Run it by itself (it waits for an MCP client on stdin/stdout):
    uv run python lessons/04_mcp_tools/support_mcp_server.py
Or over HTTP (for remote clients):
    uv run python lessons/04_mcp_tools/support_mcp_server.py http

Any MCP client can use these tools: Strands, Claude Code, Cursor, other frameworks.
That is the point of MCP: write the tool once, use it from any agent.

Note: this uses the MCP Python SDK 2.x, where FastMCP was renamed MCPServer.
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

server = MCPServer(
    name="support-desk",
    instructions="Tools for looking up orders and support tickets of the demo shop.",
)

ORDERS: dict[str, dict[str, Any]] = {
    "ORD-5521": {"status": "shipped", "carrier": "BlueDart", "eta": "2026-11-25"},
    "ORD-5530": {"status": "processing", "carrier": None, "eta": "2026-11-28"},
}
TICKETS = [
    {"id": "T-1", "customer": "C-1001", "subject": "Late delivery", "open": True},
    {"id": "T-2", "customer": "C-1002", "subject": "Wrong size", "open": False},
]


@server.tool()
def get_order_status(order_id: str) -> dict:
    """Get the shipping status, carrier and ETA of an order.

    Args:
        order_id: Order ID like ORD-5521.
    """
    order = ORDERS.get(order_id.upper())
    if order is None:
        return {"error": f"order {order_id} not found"}
    return {"order_id": order_id.upper(), **order}


@server.tool()
def list_open_tickets(customer_id: str) -> list[dict]:
    """List the open support tickets of one customer.

    Args:
        customer_id: Customer ID like C-1001.
    """
    return [t for t in TICKETS if t["customer"] == customer_id and t["open"]]


@server.tool()
def delete_ticket(ticket_id: str) -> str:
    """Permanently delete a support ticket. Dangerous: clients should filter this out."""
    return f"deleted {ticket_id}"


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "http":
        # Streamable HTTP on http://127.0.0.1:8765/mcp - put auth in front of it in production.
        server.run(transport="streamable-http", host="127.0.0.1", port=8765)
    else:
        server.run(transport="stdio")
