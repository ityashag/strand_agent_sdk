"""Lesson 11 - the three kinds of state, and who can see each one.

Run:  uv run python lessons/11_state_sessions_memory/three_kinds_of_state.py

  conversation history  agent.messages     the model SEES it    lives for the conversation
  agent state           agent.state        the model does NOT   lives for the conversation (saved by sessions)
  invocation state      invocation_state=  the model does NOT   lives for ONE call
"""

from __future__ import annotations

from strands import Agent, ToolContext, tool
from strands.models.model import Model

from course_common import build_model, setup_logging


@tool(context=True)
def add_to_cart(sku: str, quantity: int, tool_context: ToolContext) -> str:
    """Add a product to the shopping cart.

    Args:
        sku: Product SKU like SKU-WH100.
        quantity: How many units (1-10).
    """
    # agent.state: the cart survives across turns but never fills the model's context.
    cart: dict[str, int] = tool_context.agent.state.get("cart") or {}
    cart[sku] = cart.get(sku, 0) + quantity
    tool_context.agent.state.set("cart", cart)  # values must be JSON-serializable

    # invocation_state: request-scoped data from the app (e.g. who is calling).
    channel = tool_context.invocation_state.get("channel", "web")
    return f"Added {quantity} x {sku} via {channel}. Cart has {sum(cart.values())} items."


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=[add_to_cart],
        state={"cart": {}},  # initial agent state
        system_prompt="You are a shopping assistant.",
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    agent(
        "Add 2 wireless headphones (SKU-WH100) to my cart.", invocation_state={"channel": "mobile"}
    )
    agent("And one USB-C hub, SKU-UC200.", invocation_state={"channel": "mobile"})

    print("messages in history:", len(agent.messages))  # model sees these
    print("agent.state:", agent.state.get())  # model does not
    agent.state.delete("cart")  # you can also edit state from your app
    print("after delete:", agent.state.get())


if __name__ == "__main__":
    main()
