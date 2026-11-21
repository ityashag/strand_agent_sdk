"""Lesson 15 - production lifecycle controls: bound every run, stop it, know why it ended.

Run:  uv run python lessons/15_lifecycle_controls/bounded_runs.py

Every production request should have FOUR independent limits:
  turns          how many loop cycles             limits={"turns": 6}
  tokens         total / output tokens            limits={"total_tokens": 20_000}
  wall clock     a deadline that cancels the run  cancel_signal=Event + Timer
  per tool       quotas on costly tools           a hook (lesson 07)
plus a retry policy for the model provider, and a clear mapping from stop_reason to an
outcome your API can return.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum

from strands import Agent, ModelRetryStrategy
from strands.models.model import Model
from strands.types.agent import Limits
from strands.types.exceptions import (
    ConcurrencyException,
    ContextWindowOverflowException,
    MaxTokensReachedException,
)

from course_common import build_model, setup_logging
from course_common.shop import SHOP_TOOLS


class Outcome(StrEnum):
    COMPLETED = "completed"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    NEEDS_HUMAN = "needs_human"
    FAILED = "failed"


@dataclass
class Reply:
    outcome: Outcome
    text: str
    stop_reason: str | None = None
    total_tokens: int = 0


def classify(stop_reason: str) -> Outcome:
    if stop_reason in ("end_turn", "stop_sequence"):
        return Outcome.COMPLETED
    if stop_reason.startswith("limit_"):
        return Outcome.BUDGET_EXCEEDED
    if stop_reason == "cancelled":
        return Outcome.CANCELLED
    if stop_reason in ("guardrail_intervened", "content_filtered"):
        return Outcome.BLOCKED
    if stop_reason == "interrupt":
        return Outcome.NEEDS_HUMAN
    return Outcome.FAILED


class RetryTimeoutsToo(ModelRetryStrategy):
    """Default retries only throttling. Also retry plain timeouts from the provider."""

    def is_retryable(self, exception: Exception) -> bool:
        return super().is_retryable(exception) or isinstance(exception, TimeoutError)


def build_agent(model: Model | None = None, *, retry_delay: int = 2) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=SHOP_TOOLS,
        system_prompt="You are a support agent.",
        # Model call retries (throttling + timeouts): 3 attempts total, 2s -> 4s, capped at 30s.
        # Default is 6 attempts starting at 4s (4+8+16+32+64 = 2 minutes of waiting).
        # A retry strategy keeps per-turn state: create a NEW one per agent, never share it.
        retry_strategy=RetryTimeoutsToo(max_attempts=3, initial_delay=retry_delay, max_delay=30),
        callback_handler=None,
    )


def run_bounded(
    agent: Agent,
    prompt: str,
    *,
    deadline_seconds: float = 30.0,
    limits: Limits | None = None,
    request_id: str | None = None,
) -> Reply:
    """Run one request with turn/token limits, a deadline, and typed outcomes."""
    cancel = threading.Event()
    timer = threading.Timer(deadline_seconds, cancel.set)  # wall-clock deadline
    timer.start()
    try:
        result = agent(
            prompt,
            limits=limits or {"turns": 6, "total_tokens": 20_000, "output_tokens": 4_000},
            cancel_signal=cancel,
            # Same token = same logical request. A retry that arrives while the first is
            # still running waits for it and gets the SAME result instead of running twice.
            idempotency_token=request_id,
        )
    except ConcurrencyException:
        # Another request is already running on this agent instance.
        return Reply(Outcome.FAILED, "This conversation is busy. Try again in a moment.")
    except MaxTokensReachedException:
        # ONE reply hit the model's max_tokens. The partial reply is in history.
        return Reply(
            Outcome.BUDGET_EXCEEDED, "The answer was too long. Please ask for less at once."
        )
    except ContextWindowOverflowException:
        return Reply(
            Outcome.BUDGET_EXCEEDED, "This conversation is too long. Please start a new one."
        )
    finally:
        timer.cancel()

    outcome = classify(result.stop_reason)
    latest = result.metrics.latest_agent_invocation
    tokens = latest.usage.get("totalTokens", 0) if latest else 0
    text = str(result) if outcome is Outcome.COMPLETED else _message_for(outcome)
    return Reply(outcome, text, result.stop_reason, tokens)


def _message_for(outcome: Outcome) -> str:
    return {
        Outcome.BUDGET_EXCEEDED: "That request needs more work than allowed. Please narrow it down.",
        Outcome.CANCELLED: "The request took too long and was stopped.",
        Outcome.BLOCKED: "I can't help with that request.",
        Outcome.NEEDS_HUMAN: "This needs approval from a team member.",
        Outcome.FAILED: "Something went wrong.",
    }.get(outcome, "")


def main() -> None:
    setup_logging()
    agent = build_agent()
    reply = run_bounded(
        agent, "I'm C-1001. List my orders.", deadline_seconds=20, request_id="req-123"
    )
    print(reply)

    # Outside a run, any component that owns the agent can stop it:
    #   agent.cancel()   thread-safe; only call it while a run is in progress
    #   (calling it while idle cancels the NEXT run)


if __name__ == "__main__":
    main()
