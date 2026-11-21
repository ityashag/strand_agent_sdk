# Lesson 10 — Context engineering and context management

## In simple words

The **context window** is everything the model reads on one call: system prompt, tool specs, history,
tool results. It has a size limit, and you **pay for every token on every call**. A 40 KB log returned by
a tool on turn 2 is re-sent on turns 3, 4, 5... Long agents get slow, expensive, and confused.

**Context engineering** = deciding what goes into the window, when, and in what form. Four moves:

| Move | Meaning | Strands primitive |
|------|---------|-------------------|
| **Select** | Put in only what helps this call | `ContextInjector`, skills (lesson 08), memory (lesson 11) |
| **Compress** | Shrink what is already there | `ContextManager` strategies: truncate / summarize / drop |
| **Isolate** | Give sub-tasks their own window | Multi-agent (lessons 12–14) |
| **Externalize** | Move big data out, keep a reference | The **stash** + `retrieve_context` tool |

## Files

| File | What it shows |
|------|---------------|
| [context_strategies.py](context_strategies.py) | Same 40 KB-log task with no management, `"auto"`, `"agentic"`, a custom pipeline, and the classic conversation managers. |
| [context_injector.py](context_injector.py) | Inject the current time and user profile into each call without growing history. |

Measured offline with the scripted model (history size after one tool call):

| Setup | History size |
|-------|--------------|
| No management (sliding window) | 109,153 chars |
| `context_manager="auto"` | 3,425 chars |
| Custom pipeline (400-token preview) | 1,998 chars |

## The one-line default

```python
agent = Agent(context_manager="auto")
```

It turns on: offloading of large tool results to the stash (with head/tail previews), summaries of old
messages instead of dropping them, and proactive compression at ~85% of the window.

## All `context_manager=` values

| Value | What it does | When |
|-------|--------------|------|
| `None` (default) | Classic `SlidingWindowConversationManager` (or your `conversation_manager=`). | Short chats. |
| `"auto"` | Offload big results + summarize at 85% + overflow protection. | **Start here.** |
| `"agentic"` | Adds `summarize_context`, `truncate_context`, `pin_context`, `retrieve_context` tools; the model decides. | Long tasks where the model knows what matters. Costs tokens. |
| `ContextManager(strategies=[...], stash=...)` | Your own pipeline. | Tuned production agents. |
| `False` | Turn everything off. | Tests, or stateful server-side models. |

When `context_manager` is set (not `False`), `conversation_manager` is ignored.

### Building a pipeline

```python
from strands.experimental.context_manager import ContextManager, Offload

ContextManager(
    strategies=[
        Offload.truncate("tool_results", {"preview_tokens": 400}).when(threshold=2500),
        Offload.drop("tool_result_errors").when(preserve_recent=3),
        Offload.summarize("*", {"model": cheap_model, "system_prompt": "..."}).when(
            utilization=0.85, preserve_recent=8
        ),
        "overflow_protection",  # presets can be mixed in by name
    ]
)
```

| Part | Options |
|------|---------|
| Strategy | `Offload.truncate` (keep a preview), `Offload.summarize` (LLM summary, lossy, costs a call), `Offload.drop` (nothing left in context) |
| Target | `"*"`, `"tool_results"`, `"tool_result_errors"`, `"assistant_text"`, `["bash", "read_file"]` (tools by name), `["!read_file"]` (all except) |
| `.when(threshold=N)` | Fire per block bigger than N tokens |
| `.when(utilization=0.85)` | Fire when the window is 85% full (needs a known window size) |
| `.when(preserve_recent=N)` | Never touch the N newest matching messages |
| Presets | `"large_tool_offloading"`, `"proactive_summarization"`, `"overflow_protection"`, `"stale_tool_cleanup"` |
| `stash=` | Default on (in memory): originals kept + `retrieve_context` tool. `{"storage": S3Storage(...)}` to persist; `False` to discard. |

> `ContextManager` and `Offload` live in `strands.experimental.context_manager` today; the API is stable
> but will move to the main namespace.

### Classic conversation managers (still supported)

| Class | Settings |
|-------|----------|
| `SlidingWindowConversationManager` | `window_size=40` messages, `should_truncate_results=True`, `pin_first=N` (keep the first N messages), `proactive_compression` |
| `SummarizingConversationManager` | `summary_ratio=0.3`, `preserve_recent_messages=10`, `summarization_agent` / `summarization_system_prompt` |
| `NullConversationManager` | Never trims (overflow raises `ContextWindowOverflowException`) |

## `ContextInjector`

| Setting | Meaning |
|---------|---------|
| `render_content(context)` | Returns the text to add (or `None`). `context.messages`, `context.state`, `context.agent` are available. |
| `trigger="userTurn"` (default) | Inject on new user messages only. |
| `trigger="everyTurn"` | Inject before every model call (also after tool results). |
| `trigger=lambda ctx: ...` | Your own rule. |
| `name` | For logs and duplicate detection. |

The injection is stored as a marked `{"injected": ...}` block and old injections are **not** re-sent, so
facts like the time never pile up. **Escape** anything user-controlled you inject (see `profile_block`).

## Production notes

- **Measure before and after** (tokens, cost, answer quality with evals). Compression is lossy.
- **Summaries can use a cheap model** with a domain prompt that says what must be kept (IDs, numbers, decisions).
- **Keep tool results small at the source** (lesson 03). Offloading is the safety net, not the plan.
- **Persist the stash** (S3/DynamoDB storage) if sessions are resumed on other machines; otherwise offloaded
  originals are lost on restart.
- Ollama and some providers need the window size set (`context_window_limit`, `num_ctx`) or utilization
  rules cannot fire.
- Order matters: per-block truncation first, utilization-based summarization later, overflow protection last.

## Try it

1. Ask a follow-up ("what was the request id of that error?") and watch the agent call `retrieve_context`.
2. Set `stash=False` in `custom_agent` and repeat: the original is gone.
3. Change `preview_tokens` to 50 and compare answer quality with a real model.
