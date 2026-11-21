# Lesson 06 — Callbacks and streaming

## In simple words

An agent can take 10+ seconds. Users should see words and progress ("searching orders...")
as they happen, not a spinner. Strands gives you every event as it happens, in two ways:

| Way | Code | Use it for |
|-----|------|------------|
| **Callback handler** | `Agent(callback_handler=fn)` — `fn(**kwargs)` is called for each event | Scripts, CLIs, simple UIs |
| **Async iterator** | `async for event in agent.stream_async(prompt)` | Web servers (FastAPI, websockets), anything async |

The default handler prints text to stdout. That is right for a terminal demo and **wrong** for a
server, a sub-agent, or a batch job: use `callback_handler=None` there.

## Files

| File | What it shows |
|------|---------------|
| [callback_handlers.py](callback_handlers.py) | Default, buffered, silent and composite handlers; a stateful handler class. |
| [stream_events.py](stream_events.py) | `stream_async` + mapping raw events to small UI events. |
| [streaming_api.py](streaming_api.py) | FastAPI + Server-Sent Events: per-request agent, deadline, limits, cancel on disconnect. |

```bash
uv run uvicorn --app-dir lessons/06_streaming_callbacks streaming_api:app --reload
curl -N -X POST localhost:8000/chat -H 'content-type: application/json' -d '{"prompt":"Explain MCP"}'
```

## Event keys

| Key | When | Contains |
|-----|------|----------|
| `init_event_loop`, `start`, `start_event_loop` | Run / loop cycle starts | flags |
| `data` | Every text chunk | the chunk (string) |
| `delta` | Every chunk | raw delta (text, tool input, reasoning) |
| `current_tool_use` | While the model writes a tool call | `toolUseId`, `name`, partial `input` |
| `reasoningText` | Models with visible reasoning | reasoning chunk |
| `message` | A full message is added | assistant message or tool results |
| `event` | Raw provider stream event | Bedrock-style dict |
| `result` | End of the run (`stream_async` only) | the `AgentResult` |
| `force_stop`, `force_stop_reason` | Loop stopped by error/limit | reason |

## Handler settings

| Setting | What it does |
|---------|--------------|
| `callback_handler=<default>` | `PrintingCallbackHandler()` — prints text and tool names. `verbose_tool_use=False` hides tool lines. |
| `callback_handler=None` | Silent. Result still returned. |
| `CompositeCallbackHandler(a, b)` | Send events to several handlers (UI + metrics). |
| A class with `__call__(self, **kwargs)` | Keep state between events (progress, counters). |

## Production notes

- **Never forward raw events to a client.** They include the agent object, full history, system prompt
  and trace objects. Map them to a small, stable event format (`to_ui_events`).
- **One agent per request** (or per conversation with a session manager, lesson 11). Never share an
  agent between users.
- **Cancel on disconnect.** If the browser closes, set the cancel signal; otherwise you keep paying.
- **Deadline + limits on every request** (lesson 15): `cancel_signal` with a timer, and `limits=`.
- **Only the orchestrator streams.** Sub-agents use `callback_handler=None` (lesson 12).
- **Handlers must be fast and must not raise.** They run inside the loop; slow handlers slow the agent.
- Behind a proxy/load balancer, turn off response buffering for SSE (e.g. nginx `X-Accel-Buffering: no`)
  and set idle timeouts longer than your longest pause.

## Try it

1. Add `"reasoningText"` handling to `to_ui_events` and test with a reasoning model.
2. Make `ToolTracker` also record each tool's finish (look for `message` events with `toolResult`).
3. Start the API, call it with curl, and press Ctrl+C mid-answer. Check the server stops the agent.
