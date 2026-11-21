"""The shop's data access layer. Tools talk to this interface, never to a database directly.

`InMemoryShopRepository` is for local runs and tests. In production you implement the same
Protocol over your real order system (SQL, an internal API...). The agent code does not change.
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    tier: str


@dataclass
class Order:
    order_id: str
    customer_id: str
    item: str
    total: float
    status: str  # processing | shipped | delivered | refunded


@dataclass(frozen=True)
class Refund:
    refund_id: str
    order_id: str
    amount: float
    reason: str


class ShopRepository(Protocol):
    def get_customer(self, customer_id: str) -> Customer | None: ...
    def list_orders(self, customer_id: str) -> list[Order]: ...
    def get_order(self, order_id: str) -> Order | None: ...
    def create_refund(self, order_id: str, amount: float, reason: str) -> Refund: ...
    def create_ticket(self, customer_id: str, reason: str) -> str: ...


@dataclass
class InMemoryShopRepository:
    customers: dict[str, Customer] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    refunds: dict[str, Refund] = field(default_factory=dict)  # one refund per order
    tickets: list[tuple[str, str, str]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1), repr=False)

    @classmethod
    def demo(cls) -> InMemoryShopRepository:
        repo = cls()
        for c in (
            Customer("C-1001", "Asha Rao", "gold"),
            Customer("C-1002", "Ben Ortiz", "standard"),
        ):
            repo.customers[c.customer_id] = c
        for o in (
            Order("ORD-5521", "C-1001", "Wireless Headphones", 79.99, "delivered"),
            Order("ORD-5530", "C-1001", "USB-C Hub", 45.00, "shipped"),
            Order("ORD-5544", "C-1001", "Phone Case", 19.99, "delivered"),
            Order("ORD-6001", "C-1002", "4K Monitor", 349.00, "delivered"),
            Order("ORD-6002", "C-1002", "Studio Speakers", 899.00, "delivered"),
        ):
            repo.orders[o.order_id] = o
        return repo

    def get_customer(self, customer_id: str) -> Customer | None:
        return self.customers.get(customer_id)

    def list_orders(self, customer_id: str) -> list[Order]:
        return [o for o in self.orders.values() if o.customer_id == customer_id]

    def get_order(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def create_refund(self, order_id: str, amount: float, reason: str) -> Refund:
        with self._lock:  # idempotent: a second refund for the same order returns the first
            existing = self.refunds.get(order_id)
            if existing:
                return existing
            refund = Refund(f"RF-{next(self._ids):05d}", order_id, round(amount, 2), reason)
            self.refunds[order_id] = refund
            self.orders[order_id].status = "refunded"
            return refund

    def create_ticket(self, customer_id: str, reason: str) -> str:
        with self._lock:
            ticket_id = f"T-{next(self._ids):05d}"
            self.tickets.append((ticket_id, customer_id, reason))
            return ticket_id
