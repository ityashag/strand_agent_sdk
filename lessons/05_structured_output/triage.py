"""Lesson 05 - structured output: get a typed Python object back, not text.

Run:  uv run python lessons/05_structured_output/triage.py
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models.model import Model
from strands.types.exceptions import StructuredOutputException

from course_common import build_model, setup_logging


class TicketTriage(BaseModel):
    """Routing decision for one customer support message."""

    # Literal = the model can only pick one of these values.
    category: Literal["billing", "bug", "account", "other"] = Field(
        description="The team that should handle the message"
    )
    priority: Literal["low", "medium", "high"] = Field(
        description="high when the customer is blocked or losing money"
    )
    # Describe what a field MEANS, not just its type. The model reads these descriptions.
    summary: str = Field(description="One sentence describing the problem", max_length=200)
    needs_human: bool = Field(description="True if a refund over $100 or legal threat is involved")


@tool
def lookup_customer_plan(email: str) -> dict:
    """Look up a customer's name and plan by email address.

    Args:
        email: The customer's email address.
    """
    customers = {"dana@example.com": {"name": "Dana Ruiz", "plan": "enterprise"}}
    return customers.get(email, {"name": "unknown", "plan": "free"})


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(temperature=0),  # extraction: be deterministic
        tools=[lookup_customer_plan],
        system_prompt="You triage customer support messages for routing.",
        callback_handler=None,
    )


def triage(message: str, model: Model | None = None) -> TicketTriage:
    """Classify one message. A fresh agent per message: tickets never share history."""
    agent = build_agent(model)
    try:
        result = agent(
            message,
            structured_output_model=TicketTriage,
            # Each invalid answer is sent back with the validation errors and the model
            # tries again. Cap the attempts so a confused model cannot loop forever.
            limits={"structured_output_attempts": 3, "turns": 6},
        )
    except StructuredOutputException:
        # The agent could not produce a valid object: route to a person, do not crash.
        return TicketTriage(
            category="other", priority="medium", summary=message[:200], needs_human=True
        )
    if result.structured_output is None:  # e.g. a limit was reached first
        return TicketTriage(
            category="other", priority="medium", summary=message[:200], needs_human=True
        )
    assert isinstance(result.structured_output, TicketTriage)
    return result.structured_output


def main() -> None:
    setup_logging()
    for message in [
        "I was charged twice this month and need one of the charges refunded.",
        "From dana@example.com: our dashboard has been down for an hour, we are losing sales!",
    ]:
        ticket = triage(message)
        print(
            f"{ticket.priority:>6} | {ticket.category:<8} | human={ticket.needs_human} | {ticket.summary}"
        )


if __name__ == "__main__":
    main()
