"""Lesson 15: limits, deadlines, retries, concurrency - offline."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from strands import Agent, tool
from strands.types.exceptions import ModelThrottledException

from course_common import ScriptedModel, ToolCall

LOOKUP = ToolCall("lookup_customer", {"customer_id": "C-1001"})


class FlakyModel(ScriptedModel):
    """Fails `failures` times with `error`, then follows the script."""

    def __init__(self, turns, error: Exception, failures: int) -> None:
        super().__init__(turns)
        self.error, self.failures = error, failures

    async def stream(self, *args, **kwargs):
        if self.failures > 0:
            self.failures -= 1
            raise self.error
        async for event in super().stream(*args, **kwargs):
            yield event


class SlowModel(ScriptedModel):
    async def stream(self, *args, **kwargs):
        await asyncio.sleep(0.4)
        async for event in super().stream(*args, **kwargs):
            yield event


def test_turn_limit_returns_budget_exceeded(lesson):
    module = lesson("15_lifecycle_controls/bounded_runs.py")
    agent = module.build_agent(ScriptedModel([LOOKUP] * 10 + ["done"]))
    reply = module.run_bounded(agent, "loop", limits={"turns": 3})
    assert reply.outcome == module.Outcome.BUDGET_EXCEEDED and reply.stop_reason == "limit_turns"


def test_deadline_cancels_a_slow_run(lesson):
    module = lesson("15_lifecycle_controls/bounded_runs.py")

    @tool
    def slow_step(x: str) -> str:
        """A slow step.

        Args:
            x: anything
        """
        time.sleep(0.4)
        return "ok"

    model = ScriptedModel(
        [ToolCall("slow_step", {"x": "1"}), ToolCall("slow_step", {"x": "2"}), "done"]
    )
    agent = Agent(model=model, tools=[slow_step], callback_handler=None)
    reply = module.run_bounded(agent, "go", deadline_seconds=0.1)
    assert reply.outcome == module.Outcome.CANCELLED


def test_throttling_is_retried(lesson):
    module = lesson("15_lifecycle_controls/bounded_runs.py")
    model = FlakyModel(["recovered"], ModelThrottledException("slow down"), failures=2)
    reply = module.run_bounded(module.build_agent(model, retry_delay=0), "hi")
    assert reply.outcome == module.Outcome.COMPLETED and "recovered" in reply.text


def test_custom_strategy_also_retries_timeouts(lesson):
    module = lesson("15_lifecycle_controls/bounded_runs.py")
    model = FlakyModel(["ok"], TimeoutError("read timeout"), failures=1)
    assert (
        module.run_bounded(module.build_agent(model, retry_delay=0), "hi").outcome
        == module.Outcome.COMPLETED
    )


def test_busy_agent_and_idempotent_retry(lesson):
    module = lesson("15_lifecycle_controls/bounded_runs.py")
    agent = module.build_agent(SlowModel(["first answer", "should not run"]))
    replies: dict[str, Any] = {}
    worker = threading.Thread(
        target=lambda: replies.setdefault("first", module.run_bounded(agent, "x", request_id="r1"))
    )
    worker.start()
    time.sleep(0.1)
    replies["other"] = module.run_bounded(agent, "y", request_id="r2")
    replies["retry"] = module.run_bounded(agent, "x", request_id="r1")
    worker.join()

    assert replies["other"].outcome == module.Outcome.FAILED  # ConcurrencyException
    assert replies["retry"].text == replies["first"].text == "first answer\n"


def test_stop_reasons_map_to_outcomes(lesson):
    module = lesson("15_lifecycle_controls/bounded_runs.py")
    o = module.Outcome
    assert module.classify("end_turn") is o.COMPLETED
    assert module.classify("limit_total_tokens") is o.BUDGET_EXCEEDED
    assert module.classify("guardrail_intervened") is o.BLOCKED
    assert module.classify("interrupt") is o.NEEDS_HUMAN
