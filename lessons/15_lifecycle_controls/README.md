# Lesson 15 — Production lifecycle controls

## In simple words

Left alone, one request can loop too long, spend too many tokens, or keep running after the user has
left. In production every run needs **limits**, a way to **stop** it, a **retry policy** for flaky
providers, and a **clear reason** why it ended.

## Files

| File | What it shows |
|------|---------------|
| [bounded_runs.py](bounded_runs.py) | `run_bounded()`: limits + deadline + idempotency + exception handling + `stop_reason` → typed `Outcome`. A custom retry strategy. |

## 1. Limits per call

```python
result = agent(
    prompt,
    limits={
        "turns": 6,
        "total_tokens": 20_000,
        "output_tokens": 4_000,
        "structured_output_attempts": 3,
    },
)
```

| Limit | Stops when | `stop_reason` |
|-------|-----------|---------------|
| `turns` | loop cycles reach N | `limit_turns` |
| `total_tokens` | input + output tokens of this call reach N | `limit_total_tokens` |
| `output_tokens` | generated tokens reach N | `limit_output_tokens` |
| `structured_output_attempts` | N invalid structured answers | `limit_structured_output_attempts` |

Facts: limits are checked **between** turns (one turn can overshoot; tools already requested finish first),
they apply to **this call only** (the next call starts at zero), and history stays valid so you can call again
with a higher budget. Also set the model's `max_tokens` (lesson 02) to cap a single reply.

## 2. Stop a run: deadlines and cancel

```python
cancel = threading.Event()
timer = threading.Timer(30, cancel.set)
timer.start()
result = agent(prompt, cancel_signal=cancel)  # stop_reason == "cancelled" when it fires
```

| Way | Use |
|-----|-----|
| `cancel_signal=Event` per call | deadlines, client disconnect, a Stop button |
| `agent.cancel()` | another component owns the agent; thread-safe. Call it only while a run is active (when idle it cancels the **next** run). |
| Inside long tools | check `tool_context.cancel_signal.is_set()` (lesson 03). Cancellation is cooperative. |

Cancel = the run ends. Interrupt (lesson 07) = the run pauses and can resume.

## 3. Retry the model provider

| `retry_strategy=` | Behaviour |
|-------------------|-----------|
| default | Retries `ModelThrottledException` up to 6 attempts: waits 4, 8, 16, 32, 64 s. |
| `ModelRetryStrategy(max_attempts=3, initial_delay=2, max_delay=30)` | Your numbers. |
| subclass + `is_retryable(exc)` | Retry more errors (e.g. `TimeoutError`) or fewer. |
| `None` | No retries. |
| hook on `AfterModelCallEvent` → `event.retry = True` | Full custom logic (lesson 07). |

A retry strategy keeps per-turn state: **one instance per agent**. Tool failures are not model failures:
a failing tool returns an error result to the model (lesson 03), or use a retry hook (lesson 07).

## 4. One agent, many requests

| Situation | What happens | What to do |
|-----------|--------------|------------|
| Two calls on the same agent at once | 2nd raises `ConcurrencyException` (`concurrent_invocation_mode=THROW`, default) | One agent per request, or per conversation + a per-session queue |
| Client retries the same request while it runs | with `idempotency_token="req-123"`, the retry **waits and gets the same result** | Pass your request ID as the token |
| `UNSAFE_REENTRANT` mode | no guard; history can be corrupted | Don't. |

## 5. Know why it ended

| `stop_reason` | `Outcome` in `bounded_runs.py` | API response idea |
|---------------|-------------------------------|-------------------|
| `end_turn`, `stop_sequence` | `COMPLETED` | 200 + answer |
| `limit_*` | `BUDGET_EXCEEDED` | 200 + "please narrow it down" (or 413) |
| `cancelled` | `CANCELLED` | 504 / "took too long" |
| `guardrail_intervened`, `content_filtered` | `BLOCKED` | 200 + polite refusal; **don't auto-retry** |
| `interrupt` | `NEEDS_HUMAN` | 202 + approval ticket |

| Exception | Meaning |
|-----------|---------|
| `MaxTokensReachedException` | one reply exceeded the model's `max_tokens`; partial reply kept in history |
| `ContextWindowOverflowException` | history too big and the manager could not reduce it |
| `ConcurrencyException` | the agent is busy |
| `ModelThrottledException` (after retries) | provider still throttling: back off, maybe fall back (lesson 02 routing) |

## Production notes

- **Use all four limits.** A turn limit doesn't stop one slow tool; a deadline doesn't give a token budget.
- **Pass the same deadline down**: HTTP clients in tools, sub-agents (lesson 12), graph/swarm timeouts (13–14).
- **Monitor how often each limit fires** (lesson 17). Frequent `limit_turns` = prompt/tool problem; frequent
  `cancelled` = slow tools or a tight SLA.
- **The high-concurrency pattern** is a fresh agent per request (+ session manager to load history), each with
  limits, a deadline, and an idempotency token. That's what `capstone/` does.
- Retries multiply latency: 6 attempts with backoff can wait 2 minutes. Keep total retry time inside your deadline.

## Try it

1. Call `run_bounded` with `limits={"turns": 1}` on a question that needs a tool.
2. Set `deadline_seconds=0.01`: which outcome do you get?
3. Run two `run_bounded` calls on the same agent from two threads with and without the same `request_id`.
