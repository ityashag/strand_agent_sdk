"""Lessons 01-02: the loop, tools, results and model settings - all offline."""

from __future__ import annotations

from course_common import ScriptedModel, ToolCall, build_model
from course_common.config import CourseSettings


def test_loop_by_hand_calls_the_tool_then_answers(lesson):
    module = lesson("01_agent_loop/loop_by_hand.py")
    answer, history = module.run_agent("weather?")
    assert "31 C" in answer
    assert [m.get("role") for m in history] == ["user", "assistant", "user", "assistant"]


def test_simple_agent_ends_with_end_turn(lesson):
    module = lesson("01_agent_loop/simple_agent.py")
    agent = module.build_agent(ScriptedModel(["- REST has many endpoints\n- GraphQL has one"]))
    result = agent("REST vs GraphQL?")
    assert result.stop_reason == "end_turn"
    assert "GraphQL" in str(result)


def test_agent_with_tools_runs_the_tool_and_records_every_step(lesson):
    module = lesson("01_agent_loop/agent_with_tools.py")
    model = ScriptedModel(
        [ToolCall("query_product_database", {"query": "mechanical keyboard"}), "It costs $149.99."]
    )
    agent = module.build_agent(model)

    result = agent("How much is the keyboard?")

    assert result.metrics.tool_metrics["query_product_database"].success_count == 1
    tool_result = agent.messages[2]["content"][0]["toolResult"]
    assert "$149.99" in tool_result["content"][0]["text"]
    # The second model call saw the tool result: that is the loop.
    assert any("toolResult" in block for block in model.calls[1].messages[-1]["content"])


def test_unknown_product_returns_a_helpful_message_not_an_exception(lesson):
    module = lesson("01_agent_loop/agent_with_tools.py")
    text = module.query_product_database("flying car")
    assert "No product matches" in text


def test_build_model_fake_provider_needs_no_credentials():
    model = build_model(CourseSettings(model_provider="fake"))
    assert isinstance(model, ScriptedModel)


def test_bedrock_model_gets_explicit_timeouts_and_small_botocore_retries():
    from strands.models import BedrockModel

    settings = CourseSettings(
        model_provider="bedrock",
        model_id="us.amazon.nova-pro-v1:0",
        temperature=0.2,
        max_tokens=900,
    )
    model = build_model(settings)
    assert isinstance(model, BedrockModel)
    config = model.get_config()
    assert config["model_id"] == "us.amazon.nova-pro-v1:0"
    assert config["temperature"] == 0.2
    assert config["max_tokens"] == 900


class BrokenModel(ScriptedModel):
    """A model whose provider is down."""

    async def stream(self, *args, **kwargs):
        raise RuntimeError("provider unavailable")
        yield  # pragma: no cover - makes this an async generator


def test_router_falls_back_to_backup_model(lesson):
    module = lesson("02_model_providers/model_routing.py")
    backup = ScriptedModel(["Answer from the backup model."])
    agent = module.build_agent(module.build_router(primary=BrokenModel(), backup=backup))

    result = agent("hello")

    assert str(result).strip() == "Answer from the backup model."
    assert len(backup.calls) == 1


def test_providers_lesson_uses_the_same_agent_for_any_model(lesson):
    module = lesson("02_model_providers/providers.py")
    agent = module.build_agent(ScriptedModel(["loop explained"]))
    assert str(agent("explain")).strip() == "loop explained"


def test_temperature_is_not_sent_when_unset():
    from strands.models import BedrockModel

    model = build_model(CourseSettings(model_provider="bedrock", model_id="x"))
    assert isinstance(model, BedrockModel)
    assert "temperature" not in model.get_config()
