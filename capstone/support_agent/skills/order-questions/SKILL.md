---
name: order-questions
description: How to answer questions about the customer's orders and deliveries. Use for "where is my order", order lists and totals.
allowed-tools: list_my_orders get_my_profile
---

# Order questions

1. Call `list_my_orders`.
2. Answer in plain words: `processing` (being prepared), `shipped` (on the way),
   `delivered` (arrived), `refunded` (money returned).
3. Never invent tracking numbers, carriers or dates. If you don't know, say so and offer
   `escalate_to_human`.
