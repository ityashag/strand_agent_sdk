"""Lesson 08: skills, GoalLoop and a custom plugin - offline."""

from __future__ import annotations

from course_common import ScriptedModel, ToolCall
from course_common.shop import reset_shop


def test_skill_names_are_advertised_and_loaded_on_demand(lesson):
    reset_shop()
    module = lesson("08_plugins_skills/skills_agent.py")
    model = ScriptedModel([ToolCall("skills", {"skill_name": "refund-processing"}), "Let me help."])
    agent = module.build_agent(model)

    agent("I want a refund")

    assert "skills" in agent.tool_names
    # Only names + descriptions are in the prompt at start...
    system_prompt = model.calls[0].system_prompt or ""
    assert "refund-processing" in system_prompt and "order-tracking" in system_prompt
    assert "Only `delivered` orders can be refunded" not in system_prompt
    # ...the full instructions arrive when the model asks for the skill.
    loaded = agent.messages[2]["content"][0]["toolResult"]["content"][0]["text"]
    assert "Only `delivered` orders can be refunded" in loaded


def test_goal_loop_retries_with_feedback_until_valid(lesson):
    module = lesson("08_plugins_skills/goal_loop.py")
    model = ScriptedModel(
        [
            "not json at all",
            '{"title": "Crash", "severity": "urgent", "steps_to_reproduce": "upload png"}',
            '{"title": "Crash", "severity": "high", "steps_to_reproduce": "upload png"}',
        ]
    )
    agent = module.build_agent(model)

    result = agent("app crashes on upload")

    assert '"severity": "high"' in str(result)
    assert len(model.calls) == 3
    assert "Parse error" in str(model.calls[1].messages[-1])
    assert "severity must be" in str(model.calls[2].messages[-1])


def test_goal_loop_stops_after_max_attempts(lesson):
    module = lesson("08_plugins_skills/goal_loop.py")
    model = ScriptedModel(default_text="still not json")
    module.build_agent(model)("crash")
    assert len(model.calls) == 3  # max_attempts=3


def test_token_budget_plugin_refuses_after_budget(lesson):
    module = lesson("08_plugins_skills/custom_plugin.py")
    model = ScriptedModel(default_text="x" * 400)  # ~100 output tokens per answer
    agent = module.build_agent(model, max_tokens=150)

    first = agent("one")
    second = agent("two")
    third = agent("three")

    assert first.stop_reason == "end_turn" and "budget" not in str(first)
    assert agent.state.get("tokens_used") >= 150
    assert "budget" in str(third) or "budget" in str(second)
    assert "remaining_token_budget" in agent.tool_names
