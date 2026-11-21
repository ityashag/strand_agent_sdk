"""Lesson 19 - deploy to AWS Lambda (short, non-streaming requests and batch jobs).

Lambda event example:
    {"prompt": "I'm C-1001. What did I order?", "session_id": "user-7-chat-3"}

Lambda rules of thumb:
- Build heavy clients ONCE outside the handler (they survive warm starts).
- Build the AGENT per invocation (history must not leak between users).
- Keep the deadline below the Lambda timeout so you can return a clean answer.
- Package for the Lambda architecture (arm64/x86_64) and Python version you choose.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from strands import Agent
from strands.models.model import Model

from course_common import build_model, setup_logging
from course_common.shop import SHOP_TOOLS

setup_logging(json_logs=True)  # once per cold start
MODEL: Model | None = None  # created lazily, reused across warm invocations


def _model() -> Model:
    global MODEL
    if MODEL is None:
        MODEL = build_model()
    return MODEL


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    body = json.loads(event["body"]) if isinstance(event.get("body"), str) else event
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        return {"statusCode": 400, "body": json.dumps({"error": "prompt is required"})}

    # Lambda tells us how long we have left; stop the agent 5 s before Lambda kills us.
    remaining_ms = context.get_remaining_time_in_millis() if context else 60_000
    cancel = threading.Event()
    timer = threading.Timer(max(1.0, remaining_ms / 1000 - 5), cancel.set)
    timer.start()
    try:
        agent = Agent(model=_model(), tools=SHOP_TOOLS, callback_handler=None)
        result = agent(prompt, limits={"turns": 6, "total_tokens": 20_000}, cancel_signal=cancel)
    finally:
        timer.cancel()

    return {
        "statusCode": 200,
        "body": json.dumps({"answer": str(result), "stop_reason": result.stop_reason}),
    }
