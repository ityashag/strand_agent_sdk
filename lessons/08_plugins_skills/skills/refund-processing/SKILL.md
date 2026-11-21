---
name: refund-processing
description: Step-by-step procedure for refunding a customer's order. Use when a customer asks for their money back.
allowed-tools: lookup_customer get_order_history process_refund
metadata:
  owner: support-team
  version: "1.2"
---

# Refund processing

Follow these steps in order. Do not skip steps.

1. **Identify the customer.** Ask for the customer ID if you do not have it. Call `lookup_customer`.
2. **Find the order.** Call `get_order_history`. Confirm which order the customer means.
3. **Check eligibility.**
   - Only `delivered` orders can be refunded. A `shipped` order must be delivered first.
   - The refund amount must not be more than the order total.
4. **Confirm with the customer.** Say the order, item and amount, and ask "Shall I go ahead?"
   Only continue when the customer clearly says yes.
5. **Refund.** Call `process_refund` with the order ID, amount and the customer's reason.
6. **Close.** Give the refund ID and say the money arrives in 3-5 business days.

Tone: friendly, short, no promises about timelines other than the one above.
