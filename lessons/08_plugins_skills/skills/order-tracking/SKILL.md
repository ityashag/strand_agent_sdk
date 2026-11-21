---
name: order-tracking
description: How to answer "where is my order?" questions. Use when a customer asks about delivery status.
allowed-tools: lookup_customer get_order_history
---

# Order tracking

1. Get the customer ID and call `get_order_history`.
2. Find the order the customer means (by item name or order ID).
3. Reply with the status in plain words:
   - `shipped`: "It is on the way."
   - `delivered`: "It was delivered." Offer help if they did not receive it.
4. Never invent tracking numbers or dates. If you do not know, say so.
