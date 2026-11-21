"""Lesson 19 - deploy to Amazon Bedrock AgentCore Runtime.

Run locally (same HTTP contract as the cloud: POST /invocations, GET /ping, port 8080):
    uv run python lessons/19_deployment/agentcore_app.py
    curl -N localhost:8080/invocations -H 'content-type: application/json' \
         -H 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: 0f8c6a3e-demo-session-0000000000001' \
         -d '{"prompt": "I am C-1001. What did I order?"}'

AgentCore Runtime runs each SESSION in its own isolated microVM, scales for you, and sends
traces to CloudWatch. Your code only needs an entrypoint. The agent itself is unchanged.
"""

from __future__ import annotations

import os
import threading
from collections.abc import AsyncIterator
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.runtime.context import RequestContext
from strands import Agent
from strands.models.model import Model
from strands.session import SnapshotSessionManager
from strands.storage import LocalFileStorage, S3Storage
from strands.types.agent import Limits

from course_common import build_model
from course_common.shop import SHOP_TOOLS

app = BedrockAgentCoreApp()

SESSION_BUCKET = os.environ.get("SESSION_BUCKET", "")  # set in the cloud; local files otherwise
MAX_PROMPT_CHARS = 4000
LIMITS: Limits = {"turns": 8, "total_tokens": 40_000}
DEADLINE_SECONDS = 120


def build_agent(session_id: str, model: Model | None = None) -> Agent:
    storage = (
        S3Storage(bucket=SESSION_BUCKET, prefix="sessions/")
        if SESSION_BUCKET
        else LocalFileStorage("./sessions")
    )
    return Agent(
        name="support-agent",
        model=model or build_model(),
        tools=SHOP_TOOLS,
        system_prompt="You are a customer support agent. Be brief.",
        # Conversation history survives across requests and microVM restarts.
        session_manager=SnapshotSessionManager(session_id=session_id, storage=storage),
        context_manager="auto",
        trace_attributes={"session.id": session_id},
        callback_handler=None,
    )


MODEL_FACTORY: Any = None  # tests replace this with a ScriptedModel factory


@app.entrypoint
async def invoke(payload: dict[str, Any], context: RequestContext) -> AsyncIterator[dict[str, Any]]:
    """Called for every POST /invocations. Yielding makes the response a stream (SSE)."""
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        yield {"type": "error", "message": f"prompt must be 1-{MAX_PROMPT_CHARS} characters"}
        return
    # The session ID comes from the runtime header, chosen by YOUR backend (which knows
    # the authenticated user), never from the prompt or a field the end user controls.
    session_id = context.session_id or "local-dev-session"
    agent = build_agent(session_id, MODEL_FACTORY() if MODEL_FACTORY else None)

    cancel = threading.Event()
    timer = threading.Timer(DEADLINE_SECONDS, cancel.set)
    timer.start()
    try:
        async for event in agent.stream_async(prompt, limits=LIMITS, cancel_signal=cancel):
            if "data" in event:
                yield {"type": "text", "text": event["data"]}
            elif "result" in event:
                yield {"type": "done", "stop_reason": event["result"].stop_reason}
    finally:
        timer.cancel()


if __name__ == "__main__":
    app.run()  # port 8080, the port AgentCore expects
