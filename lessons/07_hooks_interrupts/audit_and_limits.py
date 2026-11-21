"""Lesson 07 - hooks: rules that run every time, no matter what the model decides.

Run:  uv run python lessons/07_hooks_interrupts/audit_and_limits.py

Three production hooks:
  AuditLog         one JSON log line per tool call (who, what, how long, ok/error)
  LimitToolCounts  per-request cap on each tool (stops runaway loops)
  RetryFlakyTools  re-run a tool that failed with a temporary error
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from typing import Any

from strands import Agent, tool
from strands.hooks import (
    AfterInvocationEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    BeforeToolCallEvent,
    HookProvider,
    HookRegistry,
)
from strands.models.model import Model

from course_common import build_model, setup_logging

log = logging.getLogger("audit")


class AuditLog(HookProvider):
    """Structured audit trail. Logs IDs and sizes, never the raw text of inputs/outputs."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.on_start)
        registry.add_callback(AfterToolCallEvent, self.on_tool_done)
        registry.add_callback(AfterInvocationEvent, self.on_end)

    def on_start(self, event: BeforeInvocationEvent) -> None:
        # invocation_state is shared by every hook and tool in this one call.
        event.invocation_state.setdefault("request_id", str(uuid.uuid4()))
        event.invocation_state["started_at"] = time.perf_counter()

    def on_tool_done(self, event: AfterToolCallEvent) -> None:
        record = {
            "event": "tool_call",
            "request_id": event.invocation_state.get("request_id"),
            "user_id": event.invocation_state.get("user_id"),
            "tool": event.tool_use["name"],
            "tool_use_id": event.tool_use["toolUseId"],
            "status": event.result.get("status"),
            "duration_ms": round((event.duration or 0) * 1000, 1),
            "input_keys": sorted(event.tool_use.get("input", {})),  # keys, not values (may be PII)
        }
        self.records.append(record)
        log.info("tool_call", extra={"fields": record})

    def on_end(self, event: AfterInvocationEvent) -> None:
        started = event.invocation_state.get("started_at", time.perf_counter())
        log.info(
            "invocation_done",
            extra={
                "fields": {
                    "request_id": event.invocation_state.get("request_id"),
                    "stop_reason": event.result.stop_reason if event.result else None,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            },
        )


class LimitToolCounts(HookProvider):
    """Cap calls per tool per request. The model is told why, so it stops trying."""

    def __init__(self, max_calls: dict[str, int], default_max: int = 10) -> None:
        self.max_calls = max_calls
        self.default_max = default_max
        self.counts: dict[str, int] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.reset)
        registry.add_callback(BeforeToolCallEvent, self.check)

    def reset(self, event: BeforeInvocationEvent) -> None:
        self.counts = {}  # limits are per request, not per agent lifetime

    def check(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        self.counts[name] = self.counts.get(name, 0) + 1
        limit = self.max_calls.get(name, self.default_max)
        if self.counts[name] > limit:
            # cancel_tool: the tool does NOT run; this text becomes the tool's error result.
            event.cancel_tool = f"'{name}' hit its limit of {limit} calls. Do NOT call it again."


class TemporaryError(Exception):
    """A failure worth retrying (timeout, 503...)."""


class RetryFlakyTools(HookProvider):
    """Re-run a tool when it fails with a temporary error, up to max_attempts."""

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts
        self.attempts: dict[str, int] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self.maybe_retry)

    def maybe_retry(self, event: AfterToolCallEvent) -> None:
        tool_id = event.tool_use["toolUseId"]
        if isinstance(event.exception, TemporaryError):
            self.attempts[tool_id] = self.attempts.get(tool_id, 1) + 1
            if self.attempts[tool_id] <= self.max_attempts:
                event.retry = True  # discard this result and run the tool again


# --- demo tools --------------------------------------------------------------------
FLAKY_STATE = {"failures_left": 2}


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city.

    Args:
        city: City name.
    """
    return f"{city}: {random.choice(['sunny', 'rainy', 'cloudy'])}"


@tool
def get_exchange_rate(currency: str) -> str:
    """Get today's USD exchange rate for a currency (the upstream API is flaky).

    Args:
        currency: ISO currency code, e.g. INR.
    """
    if FLAKY_STATE["failures_left"] > 0:
        FLAKY_STATE["failures_left"] -= 1
        raise TemporaryError("upstream timeout")
    return json.dumps({"currency": currency, "per_usd": 84.1})


def build_agent(model: Model | None = None, audit: AuditLog | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=[get_weather, get_exchange_rate],
        # Hooks are a separate layer: they do not change tools or prompts and can be
        # reused on any agent. Several hooks may listen to the same event.
        hooks=[
            audit or AuditLog(),
            LimitToolCounts({"get_weather": 3}),
            RetryFlakyTools(max_attempts=3),
        ],
        callback_handler=None,
    )


def main() -> None:
    setup_logging(json_logs=True)
    agent = build_agent()
    # A plain function also works as a hook; the event type comes from the type hint.

    def announce(event: BeforeToolCallEvent) -> None:
        print(f">> about to run {event.tool_use['name']}")

    agent.add_hook(announce)
    result = agent(
        "What's the weather in Pune, Delhi, Mumbai and Chennai? And the INR rate?",
        invocation_state={"user_id": "user-7"},
    )
    print(result)


if __name__ == "__main__":
    main()
