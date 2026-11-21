"""Lesson 11: state, sessions and memory - offline (files go to a temp folder)."""

from __future__ import annotations

import pytest

from course_common import ScriptedModel, ToolCall


def test_agent_state_holds_the_cart_and_invocation_state_the_channel(lesson):
    module = lesson("11_state_sessions_memory/three_kinds_of_state.py")
    model = ScriptedModel([ToolCall("add_to_cart", {"sku": "SKU-WH100", "quantity": 2}), "Added."])
    agent = module.build_agent(model)

    agent("add 2 headphones", invocation_state={"channel": "mobile"})

    assert agent.state.get("cart") == {"SKU-WH100": 2}
    assert "via mobile" in agent.messages[2]["content"][0]["toolResult"]["content"][0]["text"]
    assert "SKU-WH100" not in str(model.calls[0].messages)  # state is not in the prompt


@pytest.mark.parametrize("kind", ["snapshot", "record"])
def test_session_survives_a_new_agent_instance(lesson, kind):
    module = lesson("11_state_sessions_memory/sessions.py")
    first = module.build_agent("chat-1", ScriptedModel(["Hi Asha"]), kind=kind)
    first.state.set("theme", "dark")
    first("My name is Asha")

    restarted = module.build_agent("chat-1", ScriptedModel(["Your name is Asha"]), kind=kind)

    assert len(restarted.messages) == 2
    assert restarted.messages[0]["content"][0]["text"] == "My name is Asha"
    assert restarted.state.get("theme") == "dark"


def test_sessions_are_isolated_by_session_id(lesson):
    module = lesson("11_state_sessions_memory/sessions.py")
    module.build_agent("chat-asha", ScriptedModel(["ok"]))("secret: 1234")
    other = module.build_agent("chat-ben", ScriptedModel(["ok"]))
    assert other.messages == []


def test_memory_carries_across_conversations_for_the_same_user_only(lesson):
    module = lesson("11_state_sessions_memory/long_term_memory.py")
    fact = "Customer prefers contact by email, never by phone"
    module.build_agent(
        "asha", ScriptedModel([ToolCall("add_memory", {"entries": [fact]}), "Noted."])
    )("email")

    later = ScriptedModel(["We will email you."])
    module.build_agent("asha", later)("How should you contact me?")
    assert fact in str(later.calls[0].messages[-1]["content"])  # injected automatically

    stranger = ScriptedModel(["?"])
    module.build_agent("ben", stranger)("How should you contact me?")
    assert fact not in str(stranger.calls[0].messages)
