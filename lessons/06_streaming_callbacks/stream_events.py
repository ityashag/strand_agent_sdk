"""Lesson 06 - stream_async: an async iterator of events (the server-side way to stream).

Run:  uv run python lessons/06_streaming_callbacks/stream_events.py
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from strands import Agent, tool
from strands.models.model import Model

from course_common import build_model, setup_logging


@tool
def word_count(text: str) -> int:
    """Count the words in a text.

    Args:
        text: The text to count.
    """
    return len(text.split())


def build_agent(model: Model | None = None) -> Agent:
    # callback_handler=None: with stream_async YOU consume the events.
    return Agent(model=model or build_model(), tools=[word_count], callback_handler=None)


async def to_ui_events(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    """Turn raw Strands events into the few small events a UI needs.

    Never forward raw events to a browser: they contain the agent object, full message
    history and trace objects. Send only what the UI needs.
    """
    announced: set[str] = set()
    async for event in events:
        if "data" in event:
            yield {"type": "text", "text": event["data"]}
        elif "current_tool_use" in event:
            tool_use = event["current_tool_use"]
            tool_id = tool_use.get("toolUseId")
            if tool_id and tool_id not in announced:
                announced.add(tool_id)
                yield {"type": "tool", "name": tool_use.get("name")}
        elif "result" in event:
            result = event["result"]
            usage = result.metrics.accumulated_usage
            yield {
                "type": "done",
                "stop_reason": result.stop_reason,
                "total_tokens": usage.get("totalTokens", 0),
            }


async def main() -> None:
    setup_logging()
    agent = build_agent()
    events = agent.stream_async("How many words are in 'the quick brown fox'?")
    async for event in to_ui_events(events):
        if event["type"] == "text":
            print(event["text"], end="", flush=True)
        else:
            print(f"\n<{event}>")


if __name__ == "__main__":
    asyncio.run(main())
