"""Lesson 06 - a streaming HTTP API with Server-Sent Events (SSE).

Run:   uv run uvicorn --app-dir lessons/06_streaming_callbacks streaming_api:app --reload
Call:  curl -N -X POST localhost:8000/chat -H 'content-type: application/json' \
            -d '{"prompt": "Explain MCP in 3 sentences"}'

Production details shown here:
- a fresh agent per request (no shared history between users)
- SSE framing ("event:" / "data:" lines) so browsers can use EventSource
- cancel the agent when the client disconnects (no paying for answers nobody reads)
- a hard deadline and turn/token limits per request
- input size validation
"""

from __future__ import annotations

import json
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from strands import Agent
from strands.types.agent import Limits
from stream_events import build_agent, to_ui_events  # same folder

DEADLINE_SECONDS = 60
LIMITS: Limits = {"turns": 8, "total_tokens": 50_000}


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(agent_factory: Callable[[], Agent] = build_agent) -> FastAPI:
    app = FastAPI(title="Streaming agent")

    @app.post("/chat")
    async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
        agent = agent_factory()  # one agent per request
        cancel = threading.Event()
        deadline = threading.Timer(DEADLINE_SECONDS, cancel.set)

        async def stream() -> AsyncIterator[str]:
            deadline.start()
            try:
                events = agent.stream_async(body.prompt, cancel_signal=cancel, limits=LIMITS)
                async for event in to_ui_events(events):
                    if await request.is_disconnected():
                        cancel.set()  # stop the agent: nobody is listening
                        break
                    yield sse(event["type"], event)
            finally:
                deadline.cancel()

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/healthz")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app


app = create_app()
