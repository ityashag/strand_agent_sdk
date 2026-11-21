"""Lesson 09 - interventions: typed allow / deny / guide / confirm / transform decisions.

Run:  uv run python lessons/09_steering_interventions/interventions.py

Hooks let you change event objects any way you like. Interventions are a stricter layer on
top: each handler RETURNS a decision, and Strands applies it with clear rules:
  - handlers run in the order you list them
  - Deny stops the operation and skips the remaining handlers (put cheap checks first)
  - Guide feedback from several handlers is combined
  - Confirm pauses for a human (interrupt / resume, like lesson 07)
  - Transform edits the content before it continues
  - on_error decides what happens if YOUR handler crashes: fail open or fail closed
"""

from __future__ import annotations

import re
from typing import Any

from strands import Agent
from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent
from strands.interventions import (
    Confirm,
    Deny,
    Guide,
    InterventionHandler,
    OnError,
    Proceed,
    Transform,
)
from strands.models.model import Model
from strands.types.interrupt import InterruptResponseContent

from course_common import build_model, setup_logging
from course_common.shop import ORDERS, SHOP_TOOLS

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


class RefundPolicy(InterventionHandler):
    """Business rules for refunds, enforced in code (not in the prompt)."""

    name = "refund-policy"

    def __init__(self, auto_approve_limit: float = 50.0, hard_limit: float = 500.0) -> None:
        self.auto_approve_limit = auto_approve_limit
        self.hard_limit = hard_limit

    @property
    def on_error(self) -> OnError:
        return "deny"  # if this check itself crashes, block the refund (fail closed)

    def before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any) -> Any:
        if event.tool_use["name"] != "process_refund":
            return Proceed()
        args = event.tool_use.get("input", {})
        amount = float(args.get("amount", 0))
        order = ORDERS.get(str(args.get("order_id", "")).upper())
        if order is None:
            return Guide(
                feedback="That order does not exist. Check the order ID with get_order_history."
            )
        if amount > self.hard_limit:
            return Deny(
                reason=f"Refunds over ${self.hard_limit:.0f} must go to a manager. Escalate instead."
            )
        if amount > order["total"]:
            return Guide(
                feedback=f"Amount is more than the order total ${order['total']}. Use the right amount."
            )
        if amount > self.auto_approve_limit:
            return Confirm(prompt=f"Approve refund of ${amount:.2f} for {args.get('order_id')}?")
        return Proceed()


class RedactEmails(InterventionHandler):
    """Remove email addresses from tool results before the model (and logs/traces) see them."""

    name = "redact-emails"

    @property
    def on_error(self) -> OnError:
        return "deny"

    def after_tool_call(self, event: AfterToolCallEvent, **kwargs: Any) -> Any:
        def redact(e: Any) -> None:
            for block in e.result.get("content", []):
                if "text" in block:
                    block["text"] = EMAIL.sub("[email]", block["text"])

        return Transform(apply=redact)


class AuditTrail(InterventionHandler):
    """Best-effort logging: if it fails, the agent must keep working (fail open)."""

    name = "audit-trail"

    def __init__(self) -> None:
        self.seen: list[str] = []

    @property
    def on_error(self) -> OnError:
        return "proceed"

    def before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any) -> Any:
        self.seen.append(event.tool_use["name"])
        return Proceed()


def build_agent(model: Model | None = None, audit: AuditTrail | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=SHOP_TOOLS,
        # Order matters: cheap, decisive checks first.
        interventions=[audit or AuditTrail(), RefundPolicy(), RedactEmails()],
        system_prompt="You are a refund agent. Follow the refund rules you are given.",
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    result = agent("I'm C-1002. Refund my monitor order ORD-6001 in full ($349). I confirm.")
    while result.stop_reason == "interrupt":  # Confirm -> ask a human
        responses: list[InterruptResponseContent] = []
        for interrupt in result.interrupts or []:
            answer = input(f"{interrupt.reason} (y/N): ")
            responses.append(
                {"interruptResponse": {"interruptId": interrupt.id, "response": answer}}
            )
        result = agent(responses)
    print(result)


if __name__ == "__main__":
    main()
