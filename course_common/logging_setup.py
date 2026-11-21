"""Logging setup used by every lesson.

Strands logs through the standard ``logging`` module under the ``strands`` logger.
In production you want one JSON object per line (easy to search in CloudWatch, Datadog,
Loki...) and you want Strands quiet unless you are debugging.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Anything passed with logger.info("...", extra={"fields": {...}}) is added as-is.
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, default=str)


def setup_logging(
    level: str = "INFO", *, json_logs: bool = False, strands_level: str = "WARNING"
) -> None:
    """Configure the root logger once.

    Args:
        level: Level for your own code.
        json_logs: One JSON object per line (use in production).
        strands_level: Level for the SDK's own loggers. Set "DEBUG" to see the agent loop.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        JsonFormatter() if json_logs else logging.Formatter("%(levelname)s %(name)s | %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("strands").setLevel(strands_level)
    logging.getLogger("botocore").setLevel("WARNING")
    logging.getLogger("httpx").setLevel("WARNING")
