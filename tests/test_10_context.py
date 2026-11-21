"""Lesson 10: context management and injection - offline."""

from __future__ import annotations

from course_common import ScriptedModel, ToolCall

LOGS = ToolCall("read_service_logs", {"service": "payments"})


def _model() -> ScriptedModel:
    return ScriptedModel([LOGS, "First error: db pool exhausted"], context_window_limit=200_000)


def test_without_management_the_full_log_stays_in_history(lesson):
    module = lesson("10_context_management/context_strategies.py")
    agent = module.classic_agent(_model())
    agent("logs")
    assert module.history_chars(agent) > 100_000


def test_auto_offloads_big_tool_results_and_adds_retrieval(lesson):
    module = lesson("10_context_management/context_strategies.py")
    agent = module.auto_agent(_model())
    agent("logs")
    assert module.history_chars(agent) < 10_000
    assert "retrieve_context" in agent.tool_names
    text = agent.messages[2]["content"][0]["toolResult"]["content"][0]["text"]
    assert text.startswith("[Truncated")


def test_custom_pipeline_uses_a_smaller_preview(lesson):
    module = lesson("10_context_management/context_strategies.py")
    auto = module.auto_agent(_model())
    custom = module.custom_agent(_model(), summarizer=ScriptedModel(["summary"]))
    auto("logs")
    custom("logs")
    assert module.history_chars(custom) < module.history_chars(auto)


def test_agentic_mode_gives_the_model_context_tools(lesson):
    module = lesson("10_context_management/context_strategies.py")
    agent = module.agentic_agent(_model())
    assert {"summarize_context", "truncate_context", "pin_context"} <= set(agent.tool_names)


def test_injected_facts_reach_the_model_but_are_not_resent(lesson):
    module = lesson("10_context_management/context_injector.py")
    model = ScriptedModel(["one", "two"])
    agent = module.build_agent(model)

    agent("hi")
    agent("again")

    first_call = str(model.calls[0].messages[-1]["content"])
    assert "<now>" in first_call and "plan='pro'" in first_call
    # On the second call the first user message is plain again.
    assert model.calls[1].messages[0]["content"] == [{"text": "hi"}]
