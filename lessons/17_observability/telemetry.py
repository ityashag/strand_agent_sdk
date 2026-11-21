"""Lesson 17 - observability: traces, metrics and logs for every agent run.

Run (print spans to the console):
    uv run python lessons/17_observability/telemetry.py
Send to a collector / Jaeger / Langfuse / X-Ray / Datadog via OTLP:
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 uv run python lessons/17_observability/telemetry.py otlp

Strands creates OpenTelemetry spans automatically:
    invoke_agent <name>                    whole request (tokens, agent name, your attributes)
      execute_event_loop_cycle             one loop turn
        chat                               one model call (tokens, model id, latency)
        execute_tool <tool>                one tool call (name, status)
You only choose WHERE they go (exporter) and WHAT extra attributes they carry.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

from strands import Agent
from strands.models.model import Model
from strands.telemetry import StrandsTelemetry

from course_common import build_model, setup_logging
from course_common.shop import SHOP_TOOLS

log = logging.getLogger("support.telemetry")


def setup_tracing(mode: str = "console") -> StrandsTelemetry:
    """Call ONCE at process start, before creating agents.

    Environment variables that matter in production:
      OTEL_SERVICE_NAME=support-agent           service name in your tracing backend
      OTEL_EXPORTER_OTLP_ENDPOINT=https://...   where to send spans (OTLP/HTTP)
      OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer ...   auth for the collector
      OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental,gen_ai_unredacted_attributes=
          -> latest GenAI conventions AND redact prompts/answers/tool args from span attributes
             (by default message content IS recorded - think about PII before shipping)
    """
    telemetry = StrandsTelemetry()  # sets the global tracer provider
    if mode == "otlp":
        telemetry.setup_otlp_exporter()  # reads OTEL_EXPORTER_OTLP_* env vars
        telemetry.setup_meter(enable_otlp_exporter=True)  # token/latency/tool metrics
    else:
        telemetry.setup_console_exporter()
    return telemetry


def build_agent(session_id: str, user_id: str, model: Model | None = None) -> Agent:
    return Agent(
        name="support-agent",
        model=model or build_model(),
        tools=SHOP_TOOLS,
        # Added to EVERY span of this agent: filter traces by user, session, tenant, version.
        # Use IDs, never emails or names.
        trace_attributes={
            "session.id": session_id,
            "user.id": user_id,
            "app.version": "1.4.2",
            "deployment.environment": "dev",
        },
        callback_handler=None,
    )


def run_and_record(agent: Agent, prompt: str, request_id: str) -> dict[str, Any]:
    """Run once and emit ONE structured log line with the numbers you alert on."""
    result = agent(prompt, invocation_state={"request_id": request_id})
    latest = result.metrics.latest_agent_invocation
    usage: dict[str, Any] = dict(latest.usage) if latest else {}
    record = {
        "request_id": request_id,
        "stop_reason": result.stop_reason,
        "cycles": len(latest.cycles) if latest else 0,
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "cache_read_tokens": usage.get("cacheReadInputTokens", 0),
        "tools": {
            name: {
                "calls": m.call_count,
                "errors": m.error_count,
                "seconds": round(m.total_time, 3),
            }
            for name, m in result.metrics.tool_metrics.items()
        },
    }
    log.info("agent_run", extra={"fields": record})
    return record


def main() -> None:
    setup_logging(json_logs=True)
    setup_tracing(sys.argv[1] if len(sys.argv) > 1 else "console")
    agent = build_agent(session_id="s-001", user_id="u-007")
    record = run_and_record(agent, "I'm C-1001. What did I order?", request_id=str(uuid.uuid4()))
    # The full metrics summary (per cycle, per tool, traces) is also available:
    summary = agent.event_loop_metrics.get_summary()
    print(
        {k: summary[k] for k in ("total_cycles", "total_duration", "accumulated_usage")},
        record["tools"],
    )


if __name__ == "__main__":
    main()
