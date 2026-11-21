"""Lessons 05-06: structured output and streaming - offline."""

from __future__ import annotations

from fastapi.testclient import TestClient

from course_common import ScriptedModel, ToolCall


def test_structured_output_returns_a_validated_object(lesson):
    module = lesson("05_structured_output/triage.py")
    model = ScriptedModel(
        [
            ToolCall("lookup_customer_plan", {"email": "dana@example.com"}),
            ToolCall(
                "TicketTriage",
                {
                    "category": "bug",
                    "priority": "high",
                    "summary": "Dashboard down",
                    "needs_human": False,
                },
            ),
        ]
    )
    ticket = module.triage("From dana@example.com: dashboard down", model)
    assert isinstance(ticket, module.TicketTriage)
    assert (ticket.category, ticket.priority) == ("bug", "high")


def test_structured_output_retries_after_invalid_value(lesson):
    module = lesson("05_structured_output/triage.py")
    bad = {"category": "money", "priority": "high", "summary": "x", "needs_human": False}
    good = {**bad, "category": "billing"}
    model = ScriptedModel([ToolCall("TicketTriage", bad), ToolCall("TicketTriage", good)])

    ticket = module.triage("charged twice", model)

    assert ticket.category == "billing"
    # The second call saw the validation error from the first attempt.
    assert "Validation failed" in str(model.calls[1].messages[-1])


def test_structured_output_falls_back_when_model_never_complies(lesson):
    module = lesson("05_structured_output/triage.py")
    ticket = module.triage("???", ScriptedModel(default_text="I refuse to use the tool"))
    assert ticket.category == "other" and ticket.needs_human is True


def test_callback_tracker_sees_tool_calls_and_text(lesson):
    module = lesson("06_streaming_callbacks/callback_handlers.py")
    tracker = module.ToolTracker()
    model = ScriptedModel(
        [ToolCall("calculator", {"a": 2, "b": 16, "operation": "power"}), "65535"]
    )
    module.build_agent(model, handler=tracker)("2^16-1?")
    assert len(tracker.tools_started) == 1
    assert tracker.text_chunks >= 1


async def test_ui_events_are_small_and_end_with_done(lesson):
    module = lesson("06_streaming_callbacks/stream_events.py")
    model = ScriptedModel([ToolCall("word_count", {"text": "a b c"}), "There are 3 words."])
    agent = module.build_agent(model)

    events = [e async for e in module.to_ui_events(agent.stream_async("count"))]

    assert events[0] == {"type": "tool", "name": "word_count"}
    assert "".join(e["text"] for e in events if e["type"] == "text").strip() == "There are 3 words."
    assert events[-1]["type"] == "done" and events[-1]["stop_reason"] == "end_turn"
    assert all(set(e) <= {"type", "text", "name", "stop_reason", "total_tokens"} for e in events)


def test_streaming_api_returns_server_sent_events(lesson):
    module = lesson("06_streaming_callbacks/streaming_api.py")
    stream_events = lesson("06_streaming_callbacks/stream_events.py")
    app = module.create_app(lambda: stream_events.build_agent(ScriptedModel(["Hello from SSE"])))
    client = TestClient(app)

    response = client.post("/chat", json={"prompt": "hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: text" in response.text and "event: done" in response.text
    assert client.post("/chat", json={"prompt": ""}).status_code == 422
