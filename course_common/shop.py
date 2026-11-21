"""Mock customer-service tools shared by lessons 08, 09, 15 and 18.

This is the running example of the official course: a support agent that looks up a
customer, checks order history, and processes refunds. The data is in memory so every
lesson runs offline. `reset_shop()` puts the data back to its starting state (tests use it).
"""

from __future__ import annotations

import copy
from typing import Any

from strands import tool

_INITIAL_CUSTOMERS: dict[str, dict[str, Any]] = {
    "C-1001": {"name": "Asha Rao", "tier": "gold", "email": "asha@example.com"},
    "C-1002": {"name": "Ben Ortiz", "tier": "standard", "email": "ben@example.com"},
}
_INITIAL_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-5521": {
        "customer_id": "C-1001",
        "item": "Wireless Headphones",
        "total": 79.99,
        "status": "delivered",
    },
    "ORD-5530": {"customer_id": "C-1001", "item": "USB-C Hub", "total": 45.00, "status": "shipped"},
    "ORD-6001": {
        "customer_id": "C-1002",
        "item": "4K Monitor",
        "total": 349.00,
        "status": "delivered",
    },
}

CUSTOMERS: dict[str, dict[str, Any]] = {}
ORDERS: dict[str, dict[str, Any]] = {}
REFUNDS: list[dict[str, Any]] = []


def reset_shop() -> None:
    CUSTOMERS.clear()
    CUSTOMERS.update(copy.deepcopy(_INITIAL_CUSTOMERS))
    ORDERS.clear()
    ORDERS.update(copy.deepcopy(_INITIAL_ORDERS))
    REFUNDS.clear()


reset_shop()


@tool
def lookup_customer(customer_id: str) -> dict[str, Any]:
    """Look up a customer's profile (name and loyalty tier) by customer ID.

    Args:
        customer_id: Customer ID like C-1001.
    """
    customer = CUSTOMERS.get(customer_id.upper())
    if customer is None:
        raise ValueError(f"No customer {customer_id}. Ask the user to check their customer ID.")
    # Do not return the email: the model does not need it for this job (data minimisation).
    return {"customer_id": customer_id.upper(), "name": customer["name"], "tier": customer["tier"]}


@tool
def get_order_history(customer_id: str) -> list[dict[str, Any]]:
    """List a customer's orders with item, total and status.

    Args:
        customer_id: Customer ID like C-1001.
    """
    cid = customer_id.upper()
    return [{"order_id": oid, **o} for oid, o in ORDERS.items() if o["customer_id"] == cid]


@tool
def process_refund(order_id: str, amount: float, reason: str) -> dict[str, Any]:
    """Refund money for a delivered order. Only call after the customer confirmed the refund.

    Args:
        order_id: Order ID like ORD-5521.
        amount: Amount to refund in USD. Must not exceed the order total.
        reason: Short reason given by the customer.
    """
    order = ORDERS.get(order_id.upper())
    if order is None:
        raise ValueError(f"No order {order_id}.")
    if order["status"] != "delivered":
        raise ValueError(
            f"Order {order_id} is {order['status']}; only delivered orders can be refunded."
        )
    if amount <= 0 or amount > order["total"]:
        raise ValueError(f"Amount must be between 0 and {order['total']}.")
    refund = {
        "refund_id": f"RF-{len(REFUNDS) + 1:04d}",
        "order_id": order_id.upper(),
        "amount": amount,
    }
    REFUNDS.append({**refund, "reason": reason})
    order["status"] = "refunded"
    return {**refund, "eta": "3-5 business days"}


SHOP_TOOLS = [lookup_customer, get_order_history, process_refund]
