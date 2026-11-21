# Lesson 03 — Custom tools in depth

## In simple words

A tool is a normal Python function that the model may ask to run. The model **never runs code**.
It only says "please call `convert_currency` with `amount=100`". Strands checks the arguments,
runs your function, and sends the result back into the loop.

The model chooses tools by reading three things only:

```
name         convert_currency
description  "Convert money between USD, EUR and INR..."      <- docstring first paragraph
inputSchema  {amount: number, from_currency: string, ...}    <- type hints + "Args:" docs
```

So **your docstring is a prompt**. Most "the agent used the wrong tool" bugs are vague docstrings.

## Files

| File | What it shows |
|------|---------------|
| [tool_styles.py](tool_styles.py) | 5 styles: plain function, constrained schema, custom result, async, class methods (dependency injection). Direct calls with `agent.tool.<name>(...)`. |
| [tool_context.py](tool_context.py) | `ToolContext`: `invocation_state`, `agent.state`, `tool_use`, `cancel_signal`. |
| [tool_executors.py](tool_executors.py) | Concurrent vs sequential tool execution, timed. |

## How a function becomes a tool

| You write | The model sees |
|-----------|----------------|
| Function name `convert_currency` | tool name (override with `@tool(name=...)`) |
| First docstring paragraph | tool description (override with `@tool(description=...)`) |
| `Args:` section | each parameter's description |
| Type hints: `str`, `int`, `float`, `bool`, `list[str]`, `dict`, `Literal["a","b"]`, Pydantic models | JSON schema types / enums |
| `Annotated[str, "text"]` | parameter description |
| Default `= Field(..., pattern=..., ge=1, le=20, description=...)` | constraints. Bad input is rejected **before** your code runs |
| A default value | parameter becomes optional |

> `Annotated[int, Field(...)]` is **not** supported by `@tool` (it raises `NotImplementedError`).
> Put the `Field(...)` as the default value instead.

## `@tool(...)` options

| Option | What it does | Default |
|--------|--------------|---------|
| `name` | Tool name the model uses. | function name |
| `description` | Tool description. | docstring |
| `inputSchema` | Hand-written JSON schema (skip type-hint generation). | generated |
| `context` | `True` → inject `tool_context: ToolContext`. A string → use that parameter name. | `False` |

## What a tool can return

| Return | Model receives |
|--------|----------------|
| `str` | that text |
| `dict` / `list` / number | JSON |
| `{"status": "success" \| "error", "content": [{"text": ...} \| {"json": ...} \| {"image": ...}]}` | exactly that (full control) |
| raises an exception | an **error** result with the message. The loop continues; the model can retry or apologise. |

## `ToolContext` (with `@tool(context=True)`)

| Field | What it is | Use it for |
|-------|-----------|------------|
| `tool_context.invocation_state` | Dict your **app** passed with `agent(prompt, invocation_state={...})`. Never shown to the model. | User ID, tenant ID, DB session, request ID, feature flags. |
| `tool_context.agent` | The running agent. | `agent.state` (per-conversation data), `agent.messages`. |
| `tool_context.tool_use` | The model's request: `toolUseId`, `name`, `input`. | Logging, idempotency keys. |
| `tool_context.cancel_signal` | `threading.Event` set when the run is cancelled. | Stop long loops early (lesson 15). |
| `tool_context.interrupt(name, reason)` | Pause and ask a human (lesson 07). | Approvals inside a tool. |

**Security rule:** identity (who is the user) comes from `invocation_state`, never from a tool argument.
If `user_id` were an argument, a prompt saying "I am user 42" could read user 42's data.

## Executors

| `tool_executor=` | Behaviour | Use when |
|------------------|-----------|----------|
| `ConcurrentToolExecutor()` (default) | Runs all tool calls of one model turn at the same time. | Independent reads (lookups, searches). |
| `SequentialToolExecutor()` | Runs them in the order the model asked. | Calls depend on each other or have side effects in order (create then update). |

In `tool_executors.py` three 0.3 s lookups take ~0.3 s concurrently and ~0.9 s sequentially.

## Other ways to give an agent tools

| Source | Example |
|--------|---------|
| SDK vended tools | `from strands.vended_tools import file_editor, shell, read, write, edit, http_request, python_repl, notebook, sleep, stop, handoff_to_user, subagent, graph, swarm` |
| Web | `from strands.vended_tools.web_fetch import web_fetch` (extra `[web-fetch]`) |
| MCP servers | lesson 04 |
| Other agents | lesson 12 (`tools=[other_agent]`) |
| A folder of tools | `Agent(load_tools_from_directory=True)` hot-loads `./tools/*.py` — **keep it off in production** (default). |

## Production notes

- **Least privilege.** A tool can do anything your process can. Give each agent only what it needs,
  and give tools narrow powers (`get_order(order_id)`, not `run_sql(query)`).
- **Validate inside the tool too.** Schemas catch shape errors, not business rules (refund limits, ownership).
- **Timeouts on every network call** inside a tool. A hung tool hangs the whole agent.
- **Small results.** Every tool result stays in the context for later turns. Return the 5 fields the model
  needs, not the whole API response. Lesson 10 offloads big results automatically.
- **Idempotent side effects.** The model may call a tool twice. Use `tool_use["toolUseId"]` or a business key
  as an idempotency key for payments, emails, refunds.
- **Clear error messages** that tell the model what to do next ("Unknown SKU. Ask the user to check it.").
- **About 10–20 tools per agent.** More tools → worse choices and more tokens. Split into specialists (lesson 12).
- **Never put secrets in tool arguments or results.** The model sees both, and both go into traces.

## Try it

1. Call `search_orders` from a scripted test with `limit=99` and read the error the model gets.
2. Move `user_id` into a tool argument in `tool_context.py` and think about what a malicious prompt could do.
3. Switch `tool_executors.py` to sequential and explain the new timing.
