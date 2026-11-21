"""Lesson 06 - callback handlers: decide what the user sees while the agent works.

Run:  uv run python lessons/06_streaming_callbacks/callback_handlers.py

A callback handler is a function that receives **kwargs for every event:
  data              a chunk of streamed text
  current_tool_use  the tool the model is calling (name + input so far)
  message           a complete message (assistant reply or tool results)
  result            the final AgentResult
"""

from __future__ import annotations

from typing import Any

from strands import Agent, tool
from strands.handlers.callback_handler import CompositeCallbackHandler, PrintingCallbackHandler
from strands.models.model import Model

from course_common import build_model, setup_logging


@tool
def calculator(a: float, b: float, operation: str = "add") -> str:
    """Do math on two numbers.

    Args:
        a: First number.
        b: Second number.
        operation: One of "add", "subtract", "multiply", "divide", "power".
    """
    ops = {
        "add": lambda: a + b,
        "subtract": lambda: a - b,
        "multiply": lambda: a * b,
        "divide": lambda: a / b if b else "error: division by zero",
        "power": lambda: a**b,
    }
    return str(ops.get(operation, lambda: f"unknown operation {operation}")())


def buffered_handler(**kwargs: Any) -> None:
    """Ignore chunks; print only complete assistant messages."""
    message = kwargs.get("message")
    if message and message.get("role") == "assistant":
        for block in message.get("content", []):
            if "text" in block:
                print("[assistant]", block["text"])


class ToolTracker:
    """A stateful handler: remembers which tools ran (e.g. to show a progress list in a UI)."""

    def __init__(self) -> None:
        self.tools_started: list[str] = []
        self.text_chunks = 0

    def __call__(self, **kwargs: Any) -> None:
        tool_use = kwargs.get("current_tool_use")
        # current_tool_use fires many times while the input streams in; record a tool once.
        if (
            tool_use
            and tool_use.get("name")
            and tool_use.get("toolUseId") not in self.tools_started
        ):
            self.tools_started.append(tool_use["toolUseId"])
            print(f"[tool] {tool_use['name']} starting")
        if "data" in kwargs:
            self.text_chunks += 1


def build_agent(model: Model | None = None, handler: Any = None) -> Agent:
    return Agent(model=model or build_model(), tools=[calculator], callback_handler=handler)


def main() -> None:
    setup_logging()
    question = "What is 2 to the power of 16, minus 1?"

    print("1) default handler (streams text + tool names to stdout)")
    build_agent(handler=PrintingCallbackHandler())(question)

    print("\n2) buffered handler (only complete messages)")
    build_agent(handler=buffered_handler)(question)

    print("\n3) silent (callback_handler=None) - use for servers and sub-agents")
    result = build_agent(handler=None)(question)
    print("captured:", str(result).strip())

    print("\n4) several handlers at once")
    tracker = ToolTracker()
    build_agent(handler=CompositeCallbackHandler(buffered_handler, tracker))(question)
    print(
        f"tracker saw {len(tracker.tools_started)} tool call(s), {tracker.text_chunks} text chunks"
    )


if __name__ == "__main__":
    main()
