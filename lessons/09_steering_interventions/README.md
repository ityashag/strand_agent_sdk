# Lesson 09 — Steering and interventions (keep the agent on the rails)

## In simple words

Writing "always look up the customer before a refund" in the system prompt works *most* of the time.
In production "most" is not enough: refunds cost money. **Steering** and **interventions** check what the
agent is about to do, in code, at runtime, and correct it.

Strands reports that steering handlers passed 100% of 600 evaluation runs, versus about 82% for
prompt-only instructions on the same task.

| Tool for the job | Returns | Best for |
|------------------|---------|----------|
| Hook (lesson 07) | changes the event object | Logging, metrics, retries, anything custom |
| **Steering handler** (plugin) | `Proceed`, `Guide`, `Interrupt` | Workflow order, reply quality; can use a judge model |
| **Intervention handler** | `Proceed`, `Deny`, `Guide`, `Confirm`, `Transform` | Authorization, business rules, approvals, redaction — with ordering and fail-open/closed rules |

## Files

| File | What it shows |
|------|---------------|
| [steering.py](steering.py) | `RefundWorkflow` (tool order via the ledger), `NoPromisesInReplies` (check replies), `tone_guardrail` (LLM judge). |
| [interventions.py](interventions.py) | `RefundPolicy` (Guide / Deny / Confirm by amount), `RedactEmails` (Transform tool results), `AuditTrail` (fail-open). |

## Steering

| Piece | Meaning |
|-------|---------|
| `SteeringHandler(context_providers=[LedgerProvider()])` | Base class. `LedgerProvider` records every tool call (name, input, status) in `self.steering_context.data["ledger"]`. |
| `async def steer_before_tool(self, *, agent, tool_use, **kw)` | Before a tool runs. Return `Proceed`, `Guide` (tool is cancelled, reason goes to the model), or `Interrupt` (ask a human). |
| `async def steer_after_model(self, *, agent, message, stop_reason, **kw)` | After a reply. `Guide` **drops the reply** and the model answers again. |
| `LLMSteeringHandler(system_prompt=policy, model=small_model)` | A judge model applies a written policy. Use for rules you cannot code ("acknowledge frustration"). |
| `name` | Stable ID of the handler. |

## Interventions

| Action | Allowed in | Effect |
|--------|------------|--------|
| `Proceed()` | all | continue |
| `Deny(reason=...)` | before_* | block; **skip the remaining handlers** |
| `Guide(feedback=...)` | before_tool/invocation/model, after_model | cancel and give feedback (after_model: retry the reply). Feedback from all handlers is combined. |
| `Confirm(prompt=...)` | before_tool_call | pause for human approval (interrupt → resume); "no" cancels the tool |
| `Transform(apply=fn)` | all | edit the event's content in place (later handlers see the edit) |

| Lifecycle method | When |
|------------------|------|
| `before_invocation(event)` | start of a request (e.g. block banned users) |
| `before_model_call(event)` | before each model call |
| `after_model_call(event)` | after each reply (quality checks) |
| `before_tool_call(event)` | before each tool (authorization, limits, approval) |
| `after_tool_call(event)` | after each tool (redact results) |

| `on_error` | If **your handler** raises | Use for |
|------------|---------------------------|---------|
| `"throw"` (default) | the request fails | development |
| `"deny"` | treat as Deny (**fail closed**) | security, money |
| `"proceed"` | ignore the handler (**fail open**) | logging, analytics |

## Which one should I use?

- Must never happen (refund > $500, delete prod data) → **intervention `Deny`**, or a check inside the tool.
- Needs a human → **`Confirm`** (or a hook interrupt).
- Wrong order of steps, fixable by the model → **`Guide`** (steering or intervention).
- Fuzzy quality rules (tone) → **`LLMSteeringHandler`** with a cheap judge model.
- Remove sensitive data → **`Transform`** in `after_tool_call`.

## Production notes

- **Defence in depth:** the prompt asks, steering guides, interventions enforce, and the tool itself validates.
  Never rely on only the prompt for money, data deletion or access control.
- **Fail closed for security, fail open for telemetry** (`on_error`).
- **Order handlers by cost:** fast deterministic checks first, LLM judges last (a `Deny` skips the rest).
- **Bound Guide loops.** An `after_model_call` Guide makes the model answer again; Strands sets no cap. Count
  retries in your handler and switch to `Deny` (or accept) after a few.
- **`LedgerProvider` lives in memory.** A new agent instance that resumes a saved session (for example after a
  human approval in a later request) starts with an empty ledger. For rules that must survive restarts, read
  `agent.messages` instead (see `succeeded_in_history` in [capstone/support_agent/policies.py](../../capstone/support_agent/policies.py)).
- LLM judges add latency and cost on every reply: use a small model, a short policy, and measure with evals.
- Strands also ships ready-made handlers: Cedar and Dogwood authorization policies, and human-in-the-loop.

## Try it

1. In `steering.py`, require `lookup_customer` to have been called **for the same customer ID** as the refund.
2. Add a `before_invocation` intervention that denies requests containing "ignore previous instructions".
3. Set `RedactEmails.on_error` to `"proceed"` and raise inside `redact`. What changes?
