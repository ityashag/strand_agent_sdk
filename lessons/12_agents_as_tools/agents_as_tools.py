"""Lesson 12 - agents as tools: an orchestrator that calls specialist agents.

Run:  uv run python lessons/12_agents_as_tools/agents_as_tools.py

Hub and spoke. The orchestrator stays in charge: it decides when to delegate, what to
ask, and how to combine the answers. Each specialist has its OWN context window, so a
specialist can read 50 KB of noisy data and return 3 clean sentences.
"""

from __future__ import annotations

from strands import Agent, tool
from strands.models.model import Model

from course_common import build_model, setup_logging, show_result
from course_common.shop import get_order_history, lookup_customer

# --- Specialists ----------------------------------------------------------------------


def billing_specialist(model: Model | None = None) -> Agent:
    return Agent(
        name="billing_specialist",
        # The description is the ROUTING RULE: the orchestrator reads it to decide when
        # to call this agent. Say what it does and when to use it.
        description="Answers questions about a customer's orders, totals and refunds. "
        "Give it the customer ID and the question.",
        model=model or build_model(small=True),  # specialists can use a cheaper model
        tools=[lookup_customer, get_order_history],
        system_prompt="You are a billing specialist. Answer in at most 3 sentences with exact numbers.",
        callback_handler=None,  # silent: only the orchestrator talks to the user
    )


def policy_specialist(model: Model | None = None) -> Agent:
    return Agent(
        name="policy_specialist",
        description="Knows the shop's return and refund policy. Ask it policy questions only.",
        model=model or build_model(small=True),
        system_prompt="Policy: returns within 30 days of delivery; refunds take 3-5 business days; "
        "opened software is not refundable. Answer only from this policy.",
        callback_handler=None,
    )


# --- Option A: pass the agent itself as a tool ----------------------------------------


def build_orchestrator(
    model: Model | None = None,
    billing: Agent | None = None,
    policy: Agent | None = None,
) -> Agent:
    billing = billing or billing_specialist()
    policy = policy or policy_specialist()
    return Agent(
        name="support_lead",
        model=model or build_model(),
        tools=[
            # An Agent in tools=[...] becomes a tool named after agent.name, taking {"input": str}.
            # Each call starts from a clean history (preserve_context=False by default).
            billing,
            # as_tool(...) gives more control:
            #   preserve_context=True -> the specialist remembers earlier calls
            #   delegate=True         -> its answer is returned to the user as the final answer
            policy.as_tool(preserve_context=False),
        ],
        system_prompt="You lead customer support. Delegate billing facts to billing_specialist and "
        "policy questions to policy_specialist, then write one short, friendly answer.",
        callback_handler=None,
    )


# --- Option B: wrap a specialist in @tool for full control -----------------------------


@tool
def research_order_issue(customer_id: str, question: str) -> str:
    """Investigate a customer's order problem in depth and return a short finding.

    Args:
        customer_id: Customer ID like C-1001.
        question: What to find out.
    """
    # A fresh specialist per call: clean context, its own model, its own limits.
    specialist = billing_specialist()
    result = specialist(
        f"Customer {customer_id}: {question}",
        limits={"turns": 4, "total_tokens": 8_000},  # bound the sub-agent too (lesson 15)
    )
    if result.stop_reason != "end_turn":
        return f"Could not finish the investigation ({result.stop_reason})."
    return str(result)


def main() -> None:
    setup_logging()
    lead = build_orchestrator()
    result = lead("I'm C-1001. How much did I spend in total, and how long do refunds take?")
    print(result)
    show_result(result, lead.messages)


if __name__ == "__main__":
    main()
