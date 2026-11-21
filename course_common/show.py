"""Pretty-print what an agent run did. Used by lessons to make the loop visible."""

from __future__ import annotations

import json
from typing import Any

from strands.agent.agent_result import AgentResult


def show_result(result: AgentResult, messages: list[Any] | None = None) -> None:
    """Print the stop reason, token usage and (optionally) every message of the run."""
    usage = result.metrics.accumulated_usage
    print("\n--- run summary ---------------------------------------------")
    print(f"stop_reason : {result.stop_reason}")
    print(f"loop cycles : {result.metrics.cycle_count}")
    print(
        f"tokens      : in={usage.get('inputTokens', 0)} "
        f"out={usage.get('outputTokens', 0)} total={usage.get('totalTokens', 0)}"
    )
    tools = result.metrics.tool_metrics
    if tools:
        for name, metric in tools.items():
            print(
                f"tool        : {name} calls={metric.call_count} "
                f"ok={metric.success_count} errors={metric.error_count}"
            )
    if messages is not None:
        print("--- conversation (agent.messages) ---------------------------")
        for i, message in enumerate(messages):
            for block in message.get("content", []):
                kind = next(iter(block))
                value = block[kind]
                shown = value[:160] if kind == "text" else json.dumps(value, default=str)[:160]
                print(f"[{i}] {message['role']:<9} {kind:<10} {shown}")
    print("-------------------------------------------------------------\n")
