"""The agent's tools (lesson 03), designed for production:

- NO customer_id argument anywhere. The signed-in customer comes from invocation_state,
  set by the API after authentication. The model cannot ask for someone else's data.
- Every rule that matters (ownership, status, amount) is checked HERE, even though the
  policies and steering also check it: the tool is the last line of defence.
- Results are small and contain only what the model needs (no emails, no addresses).
- Refunds are idempotent (one refund per order), so a repeated call is harmless.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field
from strands import ToolContext, tool

from support_agent.data import ShopRepository


class SupportTools:
    def __init__(self, repo: ShopRepository) -> None:
        self.repo = repo

    @staticmethod
    def _customer_id(tool_context: ToolContext) -> str:
        customer_id = tool_context.invocation_state.get("customer_id")
        if not customer_id:
            raise PermissionError("No signed-in customer for this request.")
        return str(customer_id)

    @tool(context=True)
    def get_my_profile(self, tool_context: ToolContext) -> dict[str, Any]:
        """Get the signed-in customer's name and loyalty tier."""
        customer = self.repo.get_customer(self._customer_id(tool_context))
        if customer is None:
            raise LookupError("Customer profile not found.")
        return {"name": customer.name, "tier": customer.tier}

    @tool(context=True)
    def list_my_orders(self, tool_context: ToolContext) -> list[dict[str, Any]]:
        """List the signed-in customer's orders with item, total and status."""
        orders = self.repo.list_orders(self._customer_id(tool_context))
        return [
            {"order_id": o.order_id, "item": o.item, "total": o.total, "status": o.status}
            for o in orders
        ]

    @tool(context=True)
    def request_refund(
        self,
        tool_context: ToolContext,
        order_id: str = Field(..., pattern=r"^ORD-\d{4}$", description="Order ID like ORD-5521"),
        amount: float = Field(..., gt=0, description="Amount in USD, at most the order total"),
        reason: str = Field(..., min_length=3, max_length=300, description="The customer's reason"),
    ) -> dict[str, Any]:
        """Refund a delivered order of the signed-in customer. Only after the customer confirmed."""
        customer_id = self._customer_id(tool_context)
        order = self.repo.get_order(order_id)
        if order is None or order.customer_id != customer_id:
            # Same message for "missing" and "someone else's": don't reveal other orders exist.
            raise LookupError(f"Order {order_id} was not found for this customer.")
        if order.status == "refunded":
            raise ValueError(f"Order {order_id} was already refunded.")
        if order.status != "delivered":
            raise ValueError(
                f"Order {order_id} is {order.status}; only delivered orders can be refunded."
            )
        if amount > order.total:
            raise ValueError(f"Amount {amount} is more than the order total {order.total}.")
        refund = self.repo.create_refund(order_id, amount, reason)
        return {"refund_id": refund.refund_id, "amount": refund.amount, "eta": "3-5 business days"}

    @tool(context=True)
    def escalate_to_human(self, tool_context: ToolContext, reason: str) -> str:
        """Create a ticket for a human support agent when you cannot solve the problem.

        Args:
            reason: One or two sentences on what the customer needs and why you escalate.
        """
        ticket_id = self.repo.create_ticket(self._customer_id(tool_context), reason[:500])
        return f"Ticket {ticket_id} created. A human will reply within 4 business hours."

    def all(self) -> list[Any]:
        return [
            self.get_my_profile,
            self.list_my_orders,
            self.request_refund,
            self.escalate_to_human,
        ]
