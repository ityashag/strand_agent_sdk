---
name: refund-requests
description: How to handle a customer who wants money back for an order. Use for any refund, return or "charged wrongly" request.
allowed-tools: list_my_orders request_refund escalate_to_human
metadata:
  owner: support-ops
  version: "2.0"
---

# Refund requests

1. Call `list_my_orders`. Find the order the customer means. If unclear, ask which one.
2. Check it can be refunded:
   - Only `delivered` orders. A `shipped` order: explain it must arrive first.
   - Already `refunded`: say so, do not refund again.
3. Say the order, item and amount, and ask: "Shall I go ahead with this refund?"
   Continue only after a clear yes.
4. Call `request_refund` with order ID, amount and the customer's reason.
   - Some refunds need supervisor approval. If so, tell the customer it is waiting for approval.
   - If the refund is refused because it is too large, use `escalate_to_human`.
5. Give the refund ID and say the money arrives in 3-5 business days. Promise nothing else.
