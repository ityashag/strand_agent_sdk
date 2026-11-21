# Lesson 11 — State, sessions and long-term memory

## In simple words

| Kind | Where | Model sees it? | Lives for | Use it for |
|------|-------|----------------|-----------|------------|
| **Conversation history** | `agent.messages` | yes | the conversation | what was said, tool calls, results |
| **Agent state** | `agent.state` | **no** | the conversation (saved by sessions) | cart, counters, workflow step, flags |
| **Invocation state** | `agent(..., invocation_state={})` | **no** | one call | user ID, tenant, request ID, DB handle |
| **Session** | session manager + storage | – | until you delete it | resume a conversation after restart / on another server |
| **Memory** | memory manager + store | via search/injection | forever, across conversations | "Asha prefers email" |
| **Storage** | `LocalFileStorage`, `S3Storage`, DynamoDB... | – | – | the bytes underneath sessions, memory and the context stash |

Session = "continue **this** conversation". Memory = "know this user in **any** conversation".

## Files

| File | What it shows |
|------|---------------|
| [three_kinds_of_state.py](three_kinds_of_state.py) | A cart in `agent.state`, a channel in `invocation_state`, history in `agent.messages`. |
| [sessions.py](sessions.py) | `SnapshotSessionManager` and `FileSessionManager`; run it twice to see the agent remember. |
| [long_term_memory.py](long_term_memory.py) | `MemoryManager` + `FileMemoryStore` per user: `add_memory`, `search_memory`, automatic injection. |

```bash
uv run python lessons/11_state_sessions_memory/sessions.py "My name is Asha."
uv run python lessons/11_state_sessions_memory/sessions.py "What is my name?"
```

## Agent state

```python
agent = Agent(state={"cart": {}})
agent.state.set("step", "verified")  # must be JSON-serializable, else ValueError
agent.state.get("step")
agent.state.get()
agent.state.delete("step")
```

Tools reach it with `tool_context.agent.state` (lesson 03). It is **not** sent to the model, so it does not
cost tokens and the model cannot change it except through your tools.

## Session managers

| Manager | Format | Settings | Use it for |
|---------|--------|----------|------------|
| `SnapshotSessionManager` (recommended) | one snapshot of the whole agent | `session_id`, `storage=LocalFileStorage(dir) \| S3Storage(bucket, prefix)`, `save_latest_on="invocation" \| "message" \| "trigger"`, `snapshot_trigger` | single agents, Graph/Swarm, bidi agents; works with `context_manager` |
| `FileSessionManager` | one file per message | `session_id`, `storage_dir` | existing record-based sessions |
| `S3SessionManager` | same, in S3 | `session_id`, `bucket`, `prefix`, `region_name`, `boto_session` | existing record-based sessions across machines |
| AgentCore Memory session manager | managed service | memory ID, actor ID, retrieval namespaces | AWS deployments (lesson 19) |
| Community: DynamoDB storage, Valkey | – | – | low-latency production backends |

What gets saved: messages, `agent.state`, conversation/context manager state, and paused interrupts
(so a human can approve hours later, lesson 07).

> `context_manager` works only with `SnapshotSessionManager`. With `FileSessionManager` / `S3SessionManager`
> the agent raises `ValueError`; use the classic `conversation_manager` there or `context_manager=False`.

> With `save_latest_on="invocation"`, a change you make to `agent.state` **after** the last call is saved at
> the next call. Use `"message"` if you need every change on disk immediately.

## Memory

| Setting | Meaning | Default |
|---------|---------|---------|
| `MemoryManager(stores=[...])` | One or more stores (each with a `name` and `description`). | – |
| `search_tool_config` | Give the model `search_memory`. | `True` |
| `add_tool_config` | Give the model `add_memory` (it decides what to save). | `False` |
| `injection` | Search and inject relevant memories into each call automatically (`<memory>` block). | `True` |
| Store `writable` | Can the agent write to this store? | – |
| Store `max_search_results` | Results per search. | – |
| Store `extraction` | Let a model extract facts from conversations automatically. | off |

| Store | Search | Use |
|-------|--------|-----|
| `TestMemoryStore` | simple | prototypes |
| `FileMemoryStore(storage=...)` | keyword (needs shared words) | local apps, demos |
| Bedrock Knowledge Base store | semantic | production on AWS |
| AgentCore Memory, community stores | semantic + strategies | production |

## Production notes

- **One session ID per user conversation**, created by your app from the authenticated user. Never accept a
  session ID from the client without checking the user owns it, or one user can read another's chat.
- **One memory namespace per user/tenant** (here: a store folder per user). Shared stores leak data.
- **Durable storage** (S3, DynamoDB, AgentCore Memory) in the cloud. Local files disappear with the container.
- **Retention**: set TTLs / lifecycle rules and a delete path ("forget me" requests, GDPR).
- **Do not store secrets or raw sensitive data** in `agent.state` or memory; they are persisted as plain JSON.
- **Load history only from trusted storage** (lesson 16): a forged history can make the agent run tools.
- **Concurrency**: two requests for the same session at once will race. Serialize per session (queue or lock).

## Try it

1. Run `sessions.py` twice, then delete `./sessions` and run again.
2. Switch `kind="record"` and look at the files written: one per message.
3. In `long_term_memory.py`, search with words that are not in the saved memory. Why does keyword search miss it?
