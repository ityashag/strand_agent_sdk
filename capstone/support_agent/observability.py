"""Logging, audit trail and tracing (lessons 07 and 17)."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

audit_log = logging.getLogger("support.audit")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info and record.exc_info[0]:
            payload["exc_type"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        JsonFormatter() if json_logs else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("strands", "botocore", "httpx", "uvicorn.access"):
        logging.getLogger(noisy).setLevel("WARNING")


def setup_tracing() -> None:
    """Export traces/metrics over OTLP when a collector is configured (no-op otherwise)."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from strands.telemetry import StrandsTelemetry

    StrandsTelemetry().setup_otlp_exporter().setup_meter(enable_otlp_exporter=True)


class AuditHook(HookProvider):
    """One JSON line per tool call. IDs, status and timing only - never inputs or results."""

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self.on_tool_done)

    def on_tool_done(self, event: AfterToolCallEvent) -> None:
        state = event.invocation_state
        audit_log.info(
            "tool_call",
            extra={
                "fields": {
                    "request_id": state.get("request_id"),
                    "session_id": state.get("session_id"),
                    "user_id": state.get("user_id"),
                    "tool": event.tool_use["name"],
                    "status": event.result.get("status"),
                    "duration_ms": round((event.duration or 0) * 1000, 1),
                }
            },
        )
