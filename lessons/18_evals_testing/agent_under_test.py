"""Lesson 18 - the agent under test (same shop agent as earlier lessons).

A factory with an injectable model is what makes an agent testable: unit tests pass a
ScriptedModel, evals pass the real model, and production passes the configured one.
"""

from __future__ import annotations

from typing import Any

from strands import Agent
from strands.models.model import Model

from course_common import build_model
from course_common.shop import SHOP_TOOLS

SYSTEM_PROMPT = """You are a customer service agent for an electronics shop.
- Always ask for the customer ID if it is missing. Never guess it.
- Before any refund: lookup_customer, then get_order_history, then process_refund.
- Only refund after the customer confirmed. Refunds take 3-5 business days.
- If a tool fails, say so honestly. Never invent orders or amounts."""


def create_support_agent(model: Model | None = None, **kwargs: Any) -> Agent:
    return Agent(
        model=model or build_model(temperature=0),
        tools=SHOP_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
        **kwargs,
    )
