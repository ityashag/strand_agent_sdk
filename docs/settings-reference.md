# Strands settings reference (strands-agents 1.65)

Every setting of `Agent(...)` and of a call `agent(...)`, in plain words, with what to use in production.
Checked against the installed SDK source. Lesson numbers point to the runnable examples.

## `Agent(...)` constructor

### Identity and model

| Setting | What it does | Default | Production | Lesson |
|---------|--------------|---------|------------|--------|
| `model` | The LLM: a `Model` object, a `ModelRouter`, or a Bedrock model ID string. | Strands' default Bedrock model | Always pass it explicitly, with timeouts and `max_tokens`. | 02 |
| `aux_model` | Model for the SDK's side calls outside the main loop: context summaries, memory extraction, the HITL risk classifier, LLM steering, the GoalLoop judge, the `web_fetch` analyst. | the main model | A smaller, cheaper model: moves all side calls at once. | 08–11 |
| `system_prompt` | Standing instructions (string or content blocks, e.g. with cache points). | none | Short, specific; enforce critical rules in code too. | 01 |
| `name` | Agent name in traces, multi-agent tools and handoffs. | generated | Set it. | 01, 12 |
| `description` | What the agent does; orchestrators route on it. | none | Set it for any agent used as a tool. | 12 |
| `agent_id` | Stable ID inside a session. | `"default"` | Set it when you persist sessions. | 11 |

### Tools

| Setting | What it does | Default | Production | Lesson |
|---------|--------------|---------|------------|--------|
| `tools` | `@tool` functions, vended tools, `MCPClient`s, other `Agent`s, tool providers, module paths. | none | Only what this agent needs (≈10–20 max). | 03, 04 |
| `tool_executor` | `ConcurrentToolExecutor()` or `SequentialToolExecutor()` for several calls in one turn. | concurrent | Sequential when side effects depend on order. | 03 |
| `record_direct_tool_call` | Whether `agent.tool.x(...)` calls are added to history. | `True` | `False` for admin/maintenance calls. | 03 |
| `load_tools_from_directory` | Hot-load tools from `./tools/`. | `False` | Keep `False`. | 03 |
| `sandbox` | Where file/shell vended tools run (`PosixShellSandbox`, Docker, SSH...). | local, unsandboxed | Sandbox any shell/file tools. | 16 |

### Output and streaming

| Setting | What it does | Default | Production | Lesson |
|---------|--------------|---------|------------|--------|
| `callback_handler` | Receives streaming events. `None` = silent. | prints to stdout | `None` on servers and sub-agents. | 06 |
| `structured_output_model` | Default Pydantic class returned by every call. | none | Prefer per call. | 05 |
| `structured_output_prompt` | Message used when the model answered in text instead of the output tool. | built-in | Rarely needed. | 05 |

### Control layers

| Setting | What it does | Default | Production | Lesson |
|---------|--------------|---------|------------|--------|
| `hooks` | `HookProvider`s or typed functions run on lifecycle events. | none | Audit, limits, retries. | 07 |
| `plugins` | Bundles of hooks + tools (`AgentSkills`, `GoalLoop`, `ContextInjector`, steering handlers, your own). | none | Reusable company-wide behaviours. | 08, 09, 10 |
| `interventions` | `InterventionHandler`s returning Proceed / Deny / Guide / Confirm / Transform. | none | Authorization, money rules, redaction; `on_error="deny"` for security. | 09, 16 |
| `retry_strategy` | Model-call retries: `ModelRetryStrategy(max_attempts, initial_delay, max_delay)`, a subclass, or `None`. | 6 attempts, 4 s doubling | 3 attempts, short delays inside your deadline. New instance per agent. | 15 |
| `concurrent_invocation_mode` | `THROW` (default) or `UNSAFE_REENTRANT` when called while busy. | `THROW` | Keep `THROW`. | 15 |

### Memory, context and state

| Setting | What it does | Default | Production | Lesson |
|---------|--------------|---------|------------|--------|
| `messages` | Start from an existing conversation. | `[]` | Only from your own trusted storage. | 11, 16 |
| `state` | Initial `agent.state` (JSON key/value, not sent to the model). | `{}` | App data per conversation. | 11 |
| `conversation_manager` | Classic history trimming: `SlidingWindowConversationManager(window_size=40)`, `SummarizingConversationManager`, `NullConversationManager`. | sliding window (40) | Ignored when `context_manager` is set. | 10 |
| `context_manager` | `"auto"`, `"agentic"`, a `ContextManager(strategies=[...], stash=...)`, or `False`. | `None` (classic) | `"auto"` to start; tune with strategies. Snapshot sessions only. | 10 |
| `session_manager` | Persist and resume: `SnapshotSessionManager`, `FileSessionManager`, `S3SessionManager`, AgentCore Memory. | none | Snapshot + S3/DynamoDB, one session per user conversation. | 11 |
| `memory_manager` | Long-term memory across conversations (`MemoryManager(stores=[...])`). | none | One namespace per user/tenant. | 11 |
| `storage` | Default byte storage shared by sessions, memory and the context stash. | none | One durable backend (S3, DynamoDB). | 11 |
| `checkpointing` | Pause at every loop boundary with `stop_reason="checkpoint"` and a `result.checkpoint`; resume with `agent([{"checkpointResume": {"checkpoint": ...}}])`. Conversation state is not inside the checkpoint (pair it with a session/snapshot). | `False` | Durable step-by-step workflows (e.g. run each step as a separate job). | – |
| `background_tasks` | `True` or `BackgroundTasksConfig`: the model may run tools in the background and get results when they finish. | off | Only with tool limits and deadlines. | – |

### Observability

| Setting | What it does | Default | Production | Lesson |
|---------|--------------|---------|------------|--------|
| `trace_attributes` | Attributes added to every span (`session.id`, `user.id`, version...). | none | IDs only, never PII. | 17 |
| `baggage_attributes` | OpenTelemetry baggage propagated to child spans/services. | none | Request/tenant IDs across services. | 17 |

## `agent(prompt, ...)` per-call settings (also `invoke_async`, `stream_async`)

| Setting | What it does | Production | Lesson |
|---------|--------------|------------|--------|
| `prompt` | Text, content blocks (images, documents), messages, or interrupt responses. | Validate size and type before calling. | 01, 07 |
| `invocation_state` | Dict for tools/hooks for this call only; never shown to the model. | User/tenant/request IDs. | 03 |
| `limits` | `{"turns", "total_tokens", "output_tokens", "structured_output_attempts"}`. | Always set turns + tokens. | 15 |
| `cancel_signal` | `threading.Event`; set it to stop the run (`stop_reason="cancelled"`). | Deadline timer + client disconnect. | 15 |
| `idempotency_token` | Same token while running → wait and return the same result. | Your request ID. | 15 |
| `structured_output_model` | Return a validated Pydantic object for this call. | With a fallback. | 05 |
| `structured_output_prompt` | Override the "format as structured output" nudge. | Rare. | 05 |
| `invocation_context` | Run this call as part of another request (from a hook event or `tool_context.invocation_context`), sharing its limits and usage. | One token budget across a parent agent and the sub-agents it calls. | 12 |

## Useful agent methods and properties

| Name | Use |
|------|-----|
| `agent.messages` | Full history (debugging, evals). |
| `agent.state.get/set/delete` | App state. |
| `agent.tool.<name>(...)` | Call a tool directly. |
| `agent.tool_names` | Registered tool names. |
| `agent.as_tool(name, description, preserve_context, delegate)` | Use this agent as another agent's tool. |
| `agent.add_hook(fn, event_type=None, order=...)` | Register a hook after construction. |
| `agent.cancel()` | Stop the running invocation (thread-safe). |
| `agent.cleanup()` | Stop MCP clients and other resources. |
| `agent.event_loop_metrics.get_summary()` | Tokens, cycles, tool stats. |
| `agent.take_snapshot()` / `agent.load_snapshot(snapshot)` | Capture / restore the agent's state in memory (what `SnapshotSessionManager` persists). |

## Result: `AgentResult`

`stop_reason`, `message`, `metrics`, `structured_output`, `interrupts`, `state`, `checkpoint`,
`invocation_context`, and `str(result)` for the text. Stop reasons are listed in lesson 01 and mapped to
outcomes in lesson 15.
