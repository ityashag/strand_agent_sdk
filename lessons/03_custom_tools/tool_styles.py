"""Lesson 03 - every way to write a tool, from simplest to most controlled.

Run:  uv run python lessons/03_custom_tools/tool_styles.py

What the model sees for each tool is ONLY its spec: name + description + JSON schema.
Print `agent.tool_registry.get_all_tools_config()` (done in main) to see exactly that.
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any, Literal

from pydantic import Field
from strands import Agent, tool
from strands.models.model import Model

from course_common import build_model, setup_logging, show_result


# 1) Plain function. Docstring first line -> description. "Args:" -> parameter docs.
#    Type hints -> JSON schema (str, int, float, bool, list[...], dict, Literal, Pydantic models).
@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert money between USD, EUR and INR using today's fixed demo rates.

    Args:
        amount: The amount of money to convert. Must be positive.
        from_currency: ISO code of the source currency, e.g. "USD".
        to_currency: ISO code of the target currency, e.g. "INR".
    """
    rates_to_usd = {"USD": 1.0, "EUR": 1.08, "INR": 0.012}
    if amount <= 0:
        # Raising is fine: Strands catches it and sends an error result to the model,
        # which can then fix its arguments. The agent does NOT crash.
        raise ValueError("amount must be positive")
    src, dst = from_currency.upper(), to_currency.upper()
    if src not in rates_to_usd or dst not in rates_to_usd:
        raise ValueError(f"unsupported currency; use one of {sorted(rates_to_usd)}")
    usd = amount * rates_to_usd[src]
    return f"{amount:.2f} {src} = {usd / rates_to_usd[dst]:.2f} {dst}"


# 2) Richer schema. Two supported ways to describe a parameter:
#    - Annotated[type, "description"]
#    - a pydantic Field(...) as the default value, which also adds constraints
#      (pattern, ge/le, max_length...). Bad input is rejected BEFORE your code runs and the
#      validation error goes back to the model so it can fix the call.
#    (Annotated[type, Field(...)] is NOT supported by @tool and raises NotImplementedError.)
@tool
def search_orders(
    customer_id: str = Field(..., pattern=r"^C-\d{4}$", description="Customer ID like C-1001"),
    status: Annotated[
        Literal["any", "open", "shipped", "refunded"], "Filter by order status"
    ] = "any",
    limit: int = Field(5, ge=1, le=20, description="Max orders to return (1-20)"),
) -> list[dict[str, Any]]:
    """Find a customer's recent orders, newest first."""
    orders = [
        {"order_id": "ORD-5521", "status": "shipped", "total": 79.99},
        {"order_id": "ORD-5530", "status": "open", "total": 45.00},
    ]
    found = [o for o in orders if status in ("any", o["status"])]
    # Returning a dict/list is fine: Strands serializes it to JSON for the model.
    # Keep results SMALL: every character costs tokens on every later turn.
    return found[:limit]


# 3) Full control over the result, including status="error" without raising.
@tool(name="check_inventory", description="Check how many units of a SKU are in stock.")
def inventory_tool(sku: str) -> dict[str, Any]:
    stock = {"SKU-WH100": 142, "SKU-MK300": 0}
    if sku not in stock:
        return {
            "status": "error",
            "content": [{"text": f"Unknown SKU {sku}. Ask the user to check it."}],
        }
    return {"status": "success", "content": [{"json": {"sku": sku, "units": stock[sku]}}]}


# 4) Async tool: use for I/O (HTTP, DB). Concurrent tool calls then overlap instead of block.
@tool
async def fetch_shipping_eta(order_id: str) -> str:
    """Get the estimated delivery date for an order.

    Args:
        order_id: Order ID like ORD-5521.
    """
    await asyncio.sleep(0.05)  # pretend network call (always put a timeout on real ones)
    return json.dumps({"order_id": order_id, "eta": "2026-11-25"})


# 5) Tools as methods: inject clients/config (dependency injection, easy to test).
class WeatherTools:
    def __init__(self, api_base_url: str, timeout_s: float = 5.0) -> None:
        self.api_base_url = api_base_url
        self.timeout_s = timeout_s

    @tool
    def get_weather(self, city: str) -> str:
        """Get the current weather for a city.

        Args:
            city: City name, e.g. "Pune".
        """
        # A real version would call f"{self.api_base_url}?q={city}" with self.timeout_s.
        return f"{city}: 28 C, clear (from {self.api_base_url})"


SYSTEM_PROMPT = "You are a shop assistant. Use tools for every fact. Be brief."


def build_agent(model: Model | None = None) -> Agent:
    weather = WeatherTools(api_base_url="https://weather.example.com")
    return Agent(
        model=model or build_model(),
        tools=[
            convert_currency,
            search_orders,
            inventory_tool,
            fetch_shipping_eta,
            weather.get_weather,
        ],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()

    print("What the model sees (tool specs):")
    for spec in agent.tool_registry.get_all_tools_config().values():
        print(" -", spec["name"], "|", spec["description"][:70])

    # You can also call a tool yourself, without the model (handy for scripts and tests).
    # It is recorded in agent.messages unless record_direct_tool_call=False.
    direct = agent.tool.convert_currency(amount=100, from_currency="USD", to_currency="INR")
    print("\ndirect call result:", direct["content"][0]["text"])

    result = agent("Convert 100 USD to INR, then tell me the ETA for order ORD-5521.")
    print(result)
    show_result(result, agent.messages)


if __name__ == "__main__":
    main()
