# Lesson 05 — Structured output

## In simple words

Text is good for people. Your **code** needs fields: `category`, `priority`, `amount`.
With structured output you describe the fields as a Pydantic model, and the agent returns an
**instance of that model**, already validated.

```python
result = agent("I was charged twice", structured_output_model=TicketTriage)
ticket: TicketTriage = result.structured_output
```

How it works inside: Strands turns your Pydantic model into a hidden tool named after the class
(`TicketTriage`). The model "calls" it with the fields. Strands validates the fields; if they are
wrong (bad enum value, missing field) it sends the **validation errors back** and the model fixes them.
The agent can still call your normal tools first (e.g. look up the customer), then return the object.

## Files

| File | What it shows |
|------|---------------|
| [triage.py](triage.py) | Ticket triage with `Literal` enums, field descriptions, a tool call before the answer, an attempt limit and a safe fallback. |

## Settings

| Setting | Where | What it does | Default |
|---------|-------|--------------|---------|
| `structured_output_model` | `agent(...)` per call | The Pydantic class to return for **this** call. | none |
| `structured_output_model` | `Agent(...)` | Default class for **every** call of this agent. | none |
| `structured_output_prompt` | both | Message sent if the model answered in text instead of using the output tool. | "You must format the previous response as structured output." |
| `limits={"structured_output_attempts": N}` | per call | Max invalid attempts before stopping with `limit_structured_output_attempts`. | unlimited |
| `result.structured_output` | result | The validated object (or `None` if a limit stopped the run). | – |
| `StructuredOutputException` | raised | The model never produced the object. | – |

It also works with `invoke_async` and `stream_async` (the object arrives on the final `result` event),
and on a conversation: earlier turns stay text, and the last call can extract fields from the whole
history ("summarize this chat for escalation").

## How to write a good schema

| Do | Why |
|----|-----|
| Use `Literal["a", "b"]` for categories | The model can only choose valid values. |
| Add `Field(description=...)` to every field | The model reads it. Say what the field **means** and when to choose each value. |
| Add constraints (`max_length`, `ge`, `le`) | Bad values are rejected and auto-corrected. |
| Give the class a docstring | It becomes the tool description. |
| Keep it small and flat | Deep nesting and many optional fields reduce accuracy. |
| Use `temperature=0` for extraction | Same input → same output. |

## Production notes

- **Always have a fallback.** Catch `StructuredOutputException` and check for `None`; send the item to a
  human queue or a default bucket. Never let one odd message crash a batch.
- **Cap attempts** with `limits={"structured_output_attempts": 3}`. Each retry is a paid model call.
- **One fresh agent per item** in batch jobs, so items do not leak into each other's history.
- **Version your schemas.** Other services read these objects. Adding a required field is a breaking change.
- **Validate business rules in code** after you get the object (e.g. refund ≤ order total). The schema
  only guarantees shape.
- On Bedrock, `strict_tools=True` (lesson 02) adds constrained decoding for tool inputs on supported models.

## Try it

1. Remove `"account"` from the `Literal` and send an account-login message. What category comes back?
2. Read `test_structured_output_retries_after_invalid_value` in [tests/test_05_06_output_streaming.py](../../tests/test_05_06_output_streaming.py):
   the first answer has an invalid category and the second one is fixed.
