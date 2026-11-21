"""Lesson 07: hooks and interrupts - offline."""

from __future__ import annotations

from course_common import ScriptedModel, ToolCall


def _weather_calls(*cities: str) -> list[ToolCall]:
    return [ToolCall("get_weather", {"city": c}) for c in cities]


def test_limit_hook_blocks_calls_over_the_limit(lesson):
    module = lesson("07_hooks_interrupts/audit_and_limits.py")
    model = ScriptedModel([_weather_calls("A", "B", "C", "D"), "done"])
    agent = module.build_agent(model)

    agent("weather for 4 cities")

    results = [b["toolResult"] for b in agent.messages[2]["content"]]
    blocked = [r for r in results if "hit its limit" in r["content"][0]["text"]]
    assert len(blocked) == 1 and blocked[0]["status"] == "error"


def test_limit_resets_for_each_request(lesson):
    module = lesson("07_hooks_interrupts/audit_and_limits.py")
    model = ScriptedModel(
        [_weather_calls("A", "B", "C"), "ok", _weather_calls("D", "E", "F"), "ok"]
    )
    agent = module.build_agent(model)
    agent("first")
    agent("second")
    last_results = [b["toolResult"]["status"] for b in agent.messages[-2]["content"]]
    assert last_results == ["success", "success", "success"]


def test_retry_hook_reruns_a_flaky_tool_until_it_succeeds(lesson):
    module = lesson("07_hooks_interrupts/audit_and_limits.py")
    module.FLAKY_STATE["failures_left"] = 2
    audit = module.AuditLog()
    model = ScriptedModel([ToolCall("get_exchange_rate", {"currency": "INR"}), "84.1"])
    agent = module.build_agent(model, audit)

    agent("INR rate?", invocation_state={"user_id": "user-7"})

    statuses = [r["status"] for r in audit.records if r["tool"] == "get_exchange_rate"]
    assert statuses == ["error", "error", "success"]
    assert agent.messages[2]["content"][0]["toolResult"]["status"] == "success"
    assert {r["user_id"] for r in audit.records} == {"user-7"}


def test_interrupt_pauses_and_resumes_after_approval(lesson):
    module = lesson("07_hooks_interrupts/approval_interrupt.py")
    module.FILES.update({"old.log": "x"})
    agent = module.build_agent(
        ScriptedModel([ToolCall("delete_file", {"path": "old.log"}), "Deleted."])
    )

    first = agent("delete old.log")
    assert first.stop_reason == "interrupt"
    assert first.interrupts[0].reason == {"tool": "delete_file", "input": {"path": "old.log"}}
    assert "old.log" in module.FILES  # nothing deleted while waiting

    response = [{"interruptResponse": {"interruptId": first.interrupts[0].id, "response": "y"}}]
    second = agent(response)
    assert second.stop_reason == "end_turn"
    assert "old.log" not in module.FILES


def test_denied_approval_cancels_the_tool(lesson):
    module = lesson("07_hooks_interrupts/approval_interrupt.py")
    module.FILES.update({"notes.md": "ideas"})
    agent = module.build_agent(
        ScriptedModel([ToolCall("delete_file", {"path": "notes.md"}), "Not deleted."])
    )

    result = module.run_with_approvals(agent, "delete notes.md", lambda reason: "n")

    assert result.stop_reason == "end_turn"
    assert "notes.md" in module.FILES
    tool_result = agent.messages[2]["content"][0]["toolResult"]
    assert "did not approve" in tool_result["content"][0]["text"]
