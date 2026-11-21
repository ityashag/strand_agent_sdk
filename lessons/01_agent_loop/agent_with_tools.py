"""Lesson 01 - an agent with tools. Now the loop runs several times.

Run:  uv run python lessons/01_agent_loop/agent_with_tools.py

Watch the printed conversation: user -> assistant(toolUse) -> user(toolResult) -> assistant(text).
That list (agent.messages) is the first place to look when you ask "why did it do that?".
"""

from __future__ import annotations

from datetime import date

from strands import Agent, tool
from strands.models.model import Model

from course_common import build_model, setup_logging, show_result

PRODUCTS = {
    "wireless headphones": "SKU-WH100: Wireless Headphones Pro - $79.99, 142 in stock, 4.5 stars",
    "usb-c hub": "SKU-UC200: USB-C Hub 7-in-1 - $45.00, 89 in stock, 4.2 stars",
    "mechanical keyboard": "SKU-MK300: Mechanical Keyboard RGB - $149.99, 23 in stock, 4.8 stars",
}


@tool
def query_product_database(query: str) -> str:
    """Look up our products by name to get SKU, price, stock and rating.

    Args:
        query: Product name to search for, e.g. "wireless headphones" or "usb-c hub".
    """
    key = query.lower()
    matches = [info for name, info in PRODUCTS.items() if name in key or key in name]
    if matches:
        return "\n".join(matches)
    return f"No product matches '{query}'. Known products: {', '.join(PRODUCTS)}"


@tool
def today() -> str:
    """Return today's date (ISO format). Models do not know the current date."""
    return date.today().isoformat()


SYSTEM_PROMPT = """You are a product analyst for an electronics shop.
Use query_product_database for every price or stock question. Never guess numbers.
Keep answers under 80 words."""


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=[query_product_database, today],
        system_prompt=SYSTEM_PROMPT,
        name="product-analyst",
        callback_handler=None,  # silent: we print the summary ourselves
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    result = agent(
        "Is the mechanical keyboard in stock, and how much is it? Also what is today's date?"
    )
    print(result)
    show_result(result, agent.messages)


if __name__ == "__main__":
    main()
