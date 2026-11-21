"""Lessons 03-04: tool schemas, validation, ToolContext, executors and MCP - all offline."""

from __future__ import annotations

from course_common import ScriptedModel, ToolCall


def test_schema_constraints_reach_the_model(lesson):
    module = lesson("03_custom_tools/tool_styles.py")
    schema = module.search_orders.tool_spec["inputSchema"]["json"]
    assert schema["properties"]["customer_id"]["pattern"] == r"^C-\d{4}$"
    assert schema["properties"]["limit"]["maximum"] == 20
    assert schema["properties"]["status"]["enum"] == ["any", "open", "shipped", "refunded"]
    assert schema["required"] == ["customer_id"]


def test_invalid_arguments_become_an_error_result_not_a_crash(lesson):
    module = lesson("03_custom_tools/tool_styles.py")
    model = ScriptedModel(
        [ToolCall("search_orders", {"customer_id": "bad", "limit": 99}), "Please give a valid ID."]
    )
    agent = module.build_agent(model)

    result = agent("show my orders")

    tool_result = agent.messages[2]["content"][0]["toolResult"]
    assert tool_result["status"] == "error"
    assert "pattern" in tool_result["content"][0]["text"]
    assert result.stop_reason == "end_turn"


def test_custom_error_result_and_direct_tool_call(lesson):
    module = lesson("03_custom_tools/tool_styles.py")
    agent = module.build_agent(ScriptedModel())
    missing = agent.tool.check_inventory(sku="SKU-NOPE", record_direct_tool_call=False)
    assert missing["status"] == "error"
    converted = agent.tool.convert_currency(amount=100, from_currency="USD", to_currency="INR")
    assert "8333.33 INR" in converted["content"][0]["text"]


def test_invocation_state_sets_identity_and_agent_state_counts_reads(lesson):
    module = lesson("03_custom_tools/tool_context.py")
    model = ScriptedModel([ToolCall("read_my_notes"), "You prefer email."])
    agent = module.build_agent(model)

    agent("what do you know about me?", invocation_state={"user_id": "user-7"})

    text = agent.messages[2]["content"][0]["toolResult"]["content"][0]["text"]
    assert "user-7" in text and "Prefers email" in text
    assert agent.state.get("notes_reads") == 1
    # invocation_state never reaches the model
    assert "user-7" not in str(model.calls[0].messages)


def test_concurrent_executor_is_faster_than_sequential(lesson):
    module = lesson("03_custom_tools/tool_executors.py")
    concurrent = module.timed_run(sequential=False)
    sequential = module.timed_run(sequential=True)
    assert module.EVENTS[:2] == ["start a", "end a"]  # sequential order
    assert concurrent < sequential


def test_mcp_client_prefixes_and_filters_tools_and_calls_the_server(lesson):
    module = lesson("04_mcp_tools/mcp_agent.py")
    model = ScriptedModel(
        [ToolCall("support_get_order_status", {"order_id": "ORD-5521"}), "Shipped with BlueDart."]
    )
    agent = module.build_agent(model)
    try:
        agent("where is ORD-5521?")
        assert sorted(agent.tool_names) == [
            "escalate_to_human",
            "support_get_order_status",
            "support_list_open_tickets",
        ]
        text = agent.messages[2]["content"][0]["toolResult"]["content"][0]["text"]
        assert "BlueDart" in text
    finally:
        agent.cleanup()
