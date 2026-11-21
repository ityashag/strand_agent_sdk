"""Rules enforced in code, around the model (lessons 09 and 16).

RedactPayments      intervention, before_invocation: card numbers never reach the model
RefundApproval      intervention, before_tool_call: Deny / Confirm (human) / Proceed by amount
RefundWorkflow      steering, before_tool: no refund before the orders were listed
NoTimelinePromises  steering, after_model: drop replies that promise dates
"""

from __future__ import annotations

import re
from typing import Any

from strands import Agent
from strands.hooks import BeforeInvocationEvent, BeforeToolCallEvent
from strands.interventions import Confirm, Deny, InterventionHandler, OnError, Proceed, Transform
from strands.types.content import Message
from strands.types.tools import ToolUse
from strands.vended_plugins.steering import (
    Guide,
    ModelSteeringAction,
    SteeringHandler,
    ToolSteeringAction,
)
from strands.vended_plugins.steering import Proceed as SteerProceed

CARD = re.compile(r"\b(?:\d[ -]?){12,15}\d\b")


class RedactPayments(InterventionHandler):
    name = "redact-payments"

    @property
    def on_error(self) -> OnError:
        return "deny"  # never send unredacted text if redaction fails

    def before_invocation(self, event: BeforeInvocationEvent, **kwargs: Any) -> Any:
        def apply(e: Any) -> None:
            for message in e.messages or []:
                if message.get("role") == "user":
                    for block in message.get("content", []):
                        if "text" in block:
                            block["text"] = CARD.sub("[card number removed]", block["text"])

        return Transform(apply=apply) if event.messages else Proceed()


class RefundApproval(InterventionHandler):
    name = "refund-approval"

    def __init__(self, auto_approve_limit: float, hard_limit: float) -> None:
        self.auto_approve_limit = auto_approve_limit
        self.hard_limit = hard_limit

    @property
    def on_error(self) -> OnError:
        return "deny"

    def before_tool_call(self, event: BeforeToolCallEvent, **kwargs: Any) -> Any:
        if event.tool_use["name"] != "request_refund":
            return Proceed()
        args = event.tool_use.get("input", {})
        amount = float(args.get("amount", 0))
        if amount > self.hard_limit:
            return Deny(
                reason=f"Refunds over ${self.hard_limit:.0f} need a manager. Use escalate_to_human."
            )
        if amount > self.auto_approve_limit:
            return Confirm(
                prompt=f"Supervisor approval needed: refund ${amount:.2f} for {args.get('order_id')} "
                f"(reason: {str(args.get('reason', ''))[:120]})"
            )
        return Proceed()


def succeeded_in_history(agent: Agent, tool_name: str) -> bool:
    """Did `tool_name` succeed anywhere in this conversation's saved history?

    We read agent.messages (persisted by the session manager) instead of the steering
    LedgerProvider, because the ledger lives in memory: a fresh agent that resumes a paused
    run (supervisor approval in a later request) would see an empty ledger.
    """
    ids = {
        block["toolUse"]["toolUseId"]
        for message in agent.messages
        for block in message.get("content", [])
        if "toolUse" in block and block["toolUse"].get("name") == tool_name
    }
    return any(
        block["toolResult"].get("toolUseId") in ids
        and block["toolResult"].get("status") == "success"
        for message in agent.messages
        for block in message.get("content", [])
        if "toolResult" in block
    )


class RefundWorkflow(SteeringHandler):
    name = "refund-workflow"

    async def steer_before_tool(
        self, *, agent: Agent, tool_use: ToolUse, **kwargs: Any
    ) -> ToolSteeringAction:
        if tool_use.get("name") != "request_refund":
            return SteerProceed(reason="not a refund")
        if not succeeded_in_history(agent, "list_my_orders"):
            return Guide(
                reason="Call list_my_orders first and confirm the order with the customer."
            )
        return SteerProceed(reason="orders checked")


class NoTimelinePromises(SteeringHandler):
    name = "no-timeline-promises"
    BANNED = ("guarantee", "i promise", "by tomorrow", "within 24 hours")

    def __init__(self, max_retries: int = 2) -> None:
        super().__init__()
        self.max_retries = max_retries
        self.retries = 0

    async def steer_after_model(
        self, *, agent: Agent, message: Message, stop_reason: str, **kwargs: Any
    ) -> ModelSteeringAction:
        text = " ".join(b.get("text", "") for b in message.get("content", [])).lower()
        hit = next((w for w in self.BANNED if w in text), None)
        if hit and self.retries < self.max_retries:  # bounded: never loop forever
            self.retries += 1
            return Guide(
                reason=f"Don't say '{hit}'. Refunds take 3-5 business days; make no other promises."
            )
        return SteerProceed(reason="ok")
