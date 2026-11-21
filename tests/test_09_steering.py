"""Lesson 09: steering and interventions - offline."""

from __future__ import annotations

import pytest
from strands import Agent, tool

from course_common import ScriptedModel, ToolCall
from course_common.shop import REFUNDS, reset_shop

REFUND = ToolCall("process_refund", {"order_id": "ORD-5521", "amount": 79.99, "reason": "broke"})


@pytest.fixture(autouse=True)
def _fresh_shop():
    reset_shop()


def test_refund_is_guided_until_lookups_are_done(lesson):
    module = lesson("09_steering_interventions/steering.py")
    model = ScriptedModel(
        [
            REFUND,  # too early -> Guide
            ToolCall("lookup_customer", {"customer_id": "C-1001"}),
            ToolCall("get_order_history", {"customer_id": "C-1001"}),
            REFUND,  # now allowed
            "Refund RF-0001 done; 3-5 business days.",
        ]
    )
    agent = module.build_agent(model)

    agent("refund ORD-5521")

    first_result = agent.messages[2]["content"][0]["toolResult"]
    assert (
        first_result["status"] == "error"
        and "lookup_customer" in first_result["content"][0]["text"]
    )
    assert len(REFUNDS) == 1


def test_reply_with_a_promise_is_dropped_and_regenerated(lesson):
    module = lesson("09_steering_interventions/steering.py")
    model = ScriptedModel(
        ["I guarantee delivery by tomorrow!", "It should arrive in 3-5 business days."]
    )
    agent = module.build_agent(model)

    result = agent("when will it arrive?")

    assert "3-5 business days" in str(result)
    assistant_text = [
        block.get("text", "")
        for m in agent.messages
        if m["role"] == "assistant"
        for block in m["content"]
    ]
    assert not any("guarantee" in t.lower() for t in assistant_text)  # bad reply was dropped
    # The model got the guidance as feedback before it answered again.
    assert "Never promise timelines" in str(model.calls[1].messages)


def test_small_refund_proceeds_without_approval(lesson):
    module = lesson("09_steering_interventions/interventions.py")
    model = ScriptedModel(
        [ToolCall("process_refund", {"order_id": "ORD-5530", "amount": 10, "reason": "x"}), "ok"]
    )
    # ORD-5530 is only shipped -> the TOOL itself refuses (last line of defence)
    agent = module.build_agent(model)
    result = agent("refund")
    assert result.stop_reason == "end_turn"
    assert agent.messages[2]["content"][0]["toolResult"]["status"] == "error"
    assert REFUNDS == []


def test_large_refund_needs_confirmation(lesson):
    module = lesson("09_steering_interventions/interventions.py")
    call = ToolCall("process_refund", {"order_id": "ORD-6001", "amount": 349, "reason": "x"})
    agent = module.build_agent(ScriptedModel([call, "Refunded."]))

    paused = agent("refund my monitor")
    assert paused.stop_reason == "interrupt" and REFUNDS == []

    done = agent([{"interruptResponse": {"interruptId": paused.interrupts[0].id, "response": "y"}}])
    assert done.stop_reason == "end_turn" and REFUNDS[0]["amount"] == 349


def test_refund_over_hard_limit_is_denied(lesson):
    module = lesson("09_steering_interventions/interventions.py")
    call = ToolCall("process_refund", {"order_id": "ORD-6001", "amount": 600, "reason": "x"})
    agent = module.build_agent(ScriptedModel([call, "I will escalate."]))
    agent("refund 600")
    text = agent.messages[2]["content"][0]["toolResult"]["content"][0]["text"]
    assert text.startswith("DENIED") and REFUNDS == []


def test_emails_are_redacted_from_tool_results(lesson):
    module = lesson("09_steering_interventions/interventions.py")

    @tool
    def get_contact(customer_id: str) -> str:
        """Get contact details.

        Args:
            customer_id: Customer ID.
        """
        return f"{customer_id}: asha@example.com, +91 555"

    model = ScriptedModel([ToolCall("get_contact", {"customer_id": "C-1001"}), "done"])
    agent = Agent(
        model=model,
        tools=[get_contact],
        interventions=[module.RedactEmails()],
        callback_handler=None,
    )
    agent("contact?")

    text = agent.messages[2]["content"][0]["toolResult"]["content"][0]["text"]
    assert "[email]" in text and "@example.com" not in str(model.calls[1].messages)


def test_audit_intervention_sees_every_tool_call(lesson):
    module = lesson("09_steering_interventions/interventions.py")
    audit = module.AuditTrail()
    model = ScriptedModel([ToolCall("lookup_customer", {"customer_id": "C-1001"}), "hi Asha"])
    module.build_agent(model, audit)("who am I")
    assert audit.seen == ["lookup_customer"]
