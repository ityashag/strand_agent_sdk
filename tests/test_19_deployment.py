"""Lesson 19: the AgentCore entrypoint and the Lambda handler - offline."""

from __future__ import annotations

import json

from starlette.testclient import TestClient

from course_common import ScriptedModel, ToolCall

SESSION = {"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "session-0000000000000000000000000000001"}


def test_agentcore_streams_events_and_keeps_the_session(lesson):
    module = lesson("19_deployment/agentcore_app.py")
    scripts = iter(
        [
            ScriptedModel(
                [ToolCall("get_order_history", {"customer_id": "C-1001"}), "Headphones and a hub."]
            ),
            ScriptedModel(["You asked about your orders."]),
        ]
    )
    module.MODEL_FACTORY = lambda: next(scripts)
    client = TestClient(module.app)

    first = client.post("/invocations", json={"prompt": "What did I order?"}, headers=SESSION)
    second = client.post("/invocations", json={"prompt": "What did I ask before?"}, headers=SESSION)

    events = [json.loads(line[6:]) for line in first.text.splitlines() if line.startswith("data: ")]
    assert events[-1] == {"type": "done", "stop_reason": "end_turn"}
    assert "Headphones" in "".join(e.get("text", "") for e in events)
    assert second.status_code == 200
    restored = module.build_agent(
        SESSION["X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"], ScriptedModel()
    )
    assert restored.messages[0]["content"][0]["text"] == "What did I order?"


def test_agentcore_rejects_bad_input_and_answers_ping(lesson):
    module = lesson("19_deployment/agentcore_app.py")
    client = TestClient(module.app)
    assert (
        "prompt must be" in client.post("/invocations", json={"prompt": ""}, headers=SESSION).text
    )
    assert client.get("/ping").json()["status"] == "Healthy"


def test_lambda_handler_answers_and_validates(lesson):
    module = lesson("19_deployment/lambda_handler.py")

    class LambdaContext:
        def get_remaining_time_in_millis(self) -> int:
            return 30_000

    module.MODEL = ScriptedModel(["You have 2 orders."])
    ok = module.handler({"body": json.dumps({"prompt": "orders?"})}, LambdaContext())
    assert ok["statusCode"] == 200 and json.loads(ok["body"])["stop_reason"] == "end_turn"
    assert module.handler({"prompt": ""}, LambdaContext())["statusCode"] == 400
