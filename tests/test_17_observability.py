"""Lesson 17: traces and metrics - offline, with an in-memory span exporter."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from course_common import ScriptedModel, ToolCall

_EXPORTER = InMemorySpanExporter()


@pytest.fixture(scope="module", autouse=True)
def _tracing():
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    trace.set_tracer_provider(provider)  # the global provider can only be set once per process
    yield


def test_spans_cover_agent_model_and_tool_with_our_attributes(lesson):
    module = lesson("17_observability/telemetry.py")
    _EXPORTER.clear()
    model = ScriptedModel([ToolCall("get_order_history", {"customer_id": "C-1001"}), "2 orders."])
    agent = module.build_agent("s-1", "u-7", model)

    agent("what did I order?")

    spans = {span.name: span for span in _EXPORTER.get_finished_spans()}
    assert {"invoke_agent support-agent", "chat", "execute_tool get_order_history"} <= set(spans)
    root = spans["invoke_agent support-agent"]
    attributes = dict(root.attributes or {})
    assert attributes["session.id"] == "s-1" and attributes["user.id"] == "u-7"
    assert int(str(attributes["gen_ai.usage.total_tokens"])) > 0


def test_run_record_has_tokens_and_tool_counts(lesson):
    module = lesson("17_observability/telemetry.py")
    model = ScriptedModel([ToolCall("lookup_customer", {"customer_id": "NOPE"}), "Not found."])
    agent = module.build_agent("s-2", "u-8", model)

    record = module.run_and_record(agent, "who am I", request_id="req-1")

    assert record["stop_reason"] == "end_turn" and record["cycles"] == 2
    assert record["tools"]["lookup_customer"]["errors"] == 1
    assert record["input_tokens"] > 0
