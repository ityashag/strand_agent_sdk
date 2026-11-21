"""Lesson 09 - steering: check what the agent is about to do, and correct it.

Run:  uv run python lessons/09_steering_interventions/steering.py

Prompts are suggestions; long contexts make models forget them. Steering checks the
agent at runtime and returns one of:
  Proceed(reason)    let it happen
  Guide(reason)      block it and tell the model why, so it fixes itself and tries again
  Interrupt(reason)  pause for a human (tool steering only)

Two kinds:
  SteeringHandler     plain Python rules (fast, free, exact)       <- RefundWorkflow
  LLMSteeringHandler  a second model judges against a policy      <- ToneGuardrail
"""

from __future__ import annotations

from typing import Any

from strands import Agent
from strands.models.model import Model
from strands.types.content import Message
from strands.types.tools import ToolUse
from strands.vended_plugins.steering import (
    Guide,
    LedgerProvider,
    LLMSteeringHandler,
    ModelSteeringAction,
    Proceed,
    SteeringHandler,
    ToolSteeringAction,
)

from course_common import build_model, setup_logging, show_result
from course_common.shop import SHOP_TOOLS


class RefundWorkflow(SteeringHandler):
    """No refund unless the customer was looked up and their orders were checked first."""

    name = "refund-workflow"

    def __init__(self) -> None:
        # LedgerProvider records every tool call (name, input, status) in steering_context.
        super().__init__(context_providers=[LedgerProvider()])

    def _succeeded(self, tool_name: str) -> bool:
        ledger = self.steering_context.data.get("ledger") or {}
        return any(
            call["tool_name"] == tool_name and call["status"] == "success"
            for call in ledger.get("tool_calls", [])
        )

    async def steer_before_tool(
        self, *, agent: Agent, tool_use: ToolUse, **kwargs: Any
    ) -> ToolSteeringAction:
        if tool_use.get("name") != "process_refund":
            return Proceed(reason="not a refund")
        if not self._succeeded("lookup_customer"):
            return Guide(reason="Look up the customer with lookup_customer before any refund.")
        if not self._succeeded("get_order_history"):
            return Guide(reason="Check the order with get_order_history before any refund.")
        return Proceed(reason="refund workflow complete")


class NoPromisesInReplies(SteeringHandler):
    """Deterministic check on the model's reply: never promise delivery dates."""

    name = "no-promises"
    BANNED = ("guarantee", "i promise", "by tomorrow")

    async def steer_after_model(
        self, *, agent: Agent, message: Message, stop_reason: str, **kwargs: Any
    ) -> ModelSteeringAction:
        text = " ".join(b.get("text", "") for b in message.get("content", [])).lower()
        hit = next((word for word in self.BANNED if word in text), None)
        if hit:
            # Guide after a model call: the reply is dropped and the model answers again.
            return Guide(
                reason=f"Do not use '{hit}'. Never promise timelines; say '3-5 business days'."
            )
        return Proceed(reason="reply ok")


def tone_guardrail(model: Model | None = None) -> LLMSteeringHandler:
    """A second (cheaper) model judges replies against a written policy."""
    return LLMSteeringHandler(
        system_prompt="""Evaluate the customer service response against these policies:
- Don't overpromise timelines
- Acknowledge customer frustration
- Don't offer unauthorized compensation
- Keep responses concise
If a policy is violated, give specific guidance on what to fix.""",
        model=model or build_model(small=True, temperature=0),
    )


def build_agent(model: Model | None = None, *, with_llm_judge: bool = False) -> Agent:
    plugins: list[Any] = [RefundWorkflow(), NoPromisesInReplies()]
    if with_llm_judge:
        plugins.append(tone_guardrail())  # costs one extra model call per reply
    return Agent(
        model=model or build_model(),
        tools=SHOP_TOOLS,
        plugins=plugins,  # steering handlers are plugins: they stack with skills etc.
        system_prompt="You are a refund agent. Be brief and friendly.",
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    result = agent("I'm C-1001. Refund ORD-5521 ($79.99), the headphones broke. Yes, I confirm.")
    print(result)
    show_result(result, agent.messages)


if __name__ == "__main__":
    main()
