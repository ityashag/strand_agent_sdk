# Lesson 17 — Observability: traces, metrics, logs

## In simple words

When a user says "the bot gave a weird answer yesterday", you need to see **exactly** what happened:
which model calls, which tools with which inputs, how long each took, how many tokens. Strands records
this automatically as **OpenTelemetry** traces. You decide where to send them and what to add.

```
invoke_agent support-agent           (whole request: tokens, session.id, user.id)
├── execute_event_loop_cycle
│   ├── chat                          (model call: model id, tokens, latency)
│   └── execute_tool lookup_customer  (tool: name, status)
└── execute_event_loop_cycle
    └── chat
```

## Files

| File | What it shows |
|------|---------------|
| [telemetry.py](telemetry.py) | `StrandsTelemetry` console/OTLP exporters, `trace_attributes`, one structured log line per run with the numbers you alert on. |

```bash
uv run python lessons/17_observability/telemetry.py                 # spans printed to the console
docker run -d -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one   # local trace viewer
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 uv run python lessons/17_observability/telemetry.py otlp
# open http://localhost:16686
```

## Setup

| Code / variable | What it does |
|-----------------|--------------|
| `StrandsTelemetry()` | Creates and registers the global tracer provider. Call once at start-up. Pass `tracer_provider=` to use your own. |
| `.setup_console_exporter()` | Print spans (development). |
| `.setup_otlp_exporter()` | Send spans over OTLP. Needs `pip install 'strands-agents[otel]'`. |
| `.setup_meter(enable_otlp_exporter=True)` | Export metrics (tokens, cycle and tool durations). |
| `OTEL_SERVICE_NAME` | Service name in the backend (default `strands-agents`). |
| `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` | Collector URL and auth. |
| `OTEL_SEMCONV_STABILITY_OPT_IN` | Comma list: `gen_ai_latest_experimental` (newest GenAI conventions), `gen_ai_tool_definitions`, `gen_ai_span_attributes_only` (content as attributes, for backends that can't read events), `gen_ai_unredacted_attributes=<list>` (**turns on redaction**; an empty list redacts all prompts, answers, system prompts and tool args/results). |
| `Agent(trace_attributes={...})` | Added to every span: `session.id`, `user.id`, version, environment, tenant. |
| `Agent(name=...)` | Appears in `invoke_agent <name>`. |

> By default, **message content (prompts, answers, tool inputs/results) is recorded in traces.** If users can
> type personal data, turn on redaction or redact before the model (lesson 16), and restrict who can read traces.

## Metrics you get for free

`result.metrics` (and `agent.event_loop_metrics`) after each run:

| Field | Meaning |
|-------|---------|
| `latest_agent_invocation.usage` | tokens of **this** call: `inputTokens`, `outputTokens`, `totalTokens`, `cacheReadInputTokens`, `cacheWriteInputTokens` |
| `accumulated_usage` | tokens over all calls of this agent |
| `cycle_count`, `latest_agent_invocation.cycles` | loop turns |
| `tool_metrics[name]` | `call_count`, `success_count`, `error_count`, `total_time` |
| `get_summary()` | everything as a dict (durations, per-cycle data, traces) |

## What to put on a dashboard and alert on

| Signal | Why |
|--------|-----|
| Requests, p50/p95 latency, error rate | basic health |
| `stop_reason` counts (`limit_*`, `cancelled`, `guardrail_intervened`, `interrupt`) | budget and safety problems |
| Tokens and cost per request / per user / per tenant | cost control, abuse detection |
| Cache read tokens ÷ input tokens | is prompt caching working? |
| Tool calls, tool error rate, tool latency (per tool) | broken integrations |
| Loop cycles per request | prompt/tool design problems (high = confused agent) |
| Model throttling and retries | quota/capacity |

## Production notes

- **One trace per request, correlated with logs**: put the same `request_id`/`session.id` in trace attributes,
  `invocation_state` and log lines.
- **Logs: one JSON line per run** with IDs, stop reason, tokens and tool counts. Never log raw prompts or
  tool results by default (`course_common/logging_setup.py`, lesson 07).
- **Sample wisely**: keep 100% of errored or limited runs, sample successful ones if volume is high.
- **AgentCore Runtime** sends traces to CloudWatch (GenAI observability) automatically when deployed (lesson 19).
- Evals can read these traces later (lesson 18): production traces become test cases.

## Try it

1. Start Jaeger, run with `otlp`, and find the `execute_tool` span for `get_order_history`.
2. Add `"tenant.id"` to `trace_attributes` and filter by it.
3. Set `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental,gen_ai_unredacted_attributes=` and check the
   prompts are gone from span attributes.
