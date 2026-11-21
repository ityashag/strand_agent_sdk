"""Lesson 03 - tool executors: run several tool calls in parallel or one by one.

Run:  uv run python lessons/03_custom_tools/tool_executors.py

When the model asks for several tools in ONE turn:
  ConcurrentToolExecutor (default) runs them at the same time  -> faster
  SequentialToolExecutor runs them in order                     -> safe for dependent side effects
"""

from __future__ import annotations

import time

from strands import Agent, tool
from strands.models.model import Model
from strands.tools.executors import ConcurrentToolExecutor, SequentialToolExecutor

from course_common import ScriptedModel, ToolCall, build_model, setup_logging

EVENTS: list[str] = []


@tool
async def slow_lookup(name: str) -> str:
    """Look up a record (takes about 0.3 s).

    Args:
        name: Record name.
    """
    import asyncio

    EVENTS.append(f"start {name}")
    await asyncio.sleep(0.3)
    EVENTS.append(f"end {name}")
    return f"{name}: ok"


def build_agent(model: Model | None = None, *, sequential: bool = False) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=[slow_lookup],
        tool_executor=SequentialToolExecutor() if sequential else ConcurrentToolExecutor(),
        callback_handler=None,
    )


def timed_run(sequential: bool) -> float:
    EVENTS.clear()
    # A scripted model that asks for three lookups in one turn, then answers.
    model = ScriptedModel(
        [[ToolCall("slow_lookup", {"name": n}) for n in ("a", "b", "c")], "All three are ok."]
    )
    agent = build_agent(model, sequential=sequential)
    start = time.perf_counter()
    agent("look up a, b and c")
    return time.perf_counter() - start


def main() -> None:
    setup_logging()
    print(f"concurrent: {timed_run(sequential=False):.2f}s  order={EVENTS}")
    print(f"sequential: {timed_run(sequential=True):.2f}s  order={EVENTS}")
    # With a real model, try:
    if build_model().get_config().get("model_id") != "scripted-model":
        print(build_agent()("Look up records a, b and c."))


if __name__ == "__main__":
    main()
