# Production checklist for a Strands agent

Go through this before real users touch your agent. Each line points to the lesson that shows how.
The [capstone](../capstone) does all of these except the ones marked "your platform".

## 1. Model

- [ ] Model ID pinned in config (not the SDK default); inference profile on Bedrock. *(02)*
- [ ] `max_tokens`, connect/read timeouts, small client retries set. *(02)*
- [ ] Prompt caching on for long system prompts / many tools. *(02)*
- [ ] Fallback model (other region/provider) through `ModelRouter`. *(02)*
- [ ] Low temperature for tool-using agents. *(02)*
- [ ] Model chosen by **evals**, not by vibes. *(18)*

## 2. Tools

- [ ] Each agent has only the tools it needs; no generic shell/SQL/HTTP without a sandbox. *(03, 16)*
- [ ] Clear docstrings and argument descriptions; constraints in the schema. *(03)*
- [ ] Identity from `invocation_state`, never from tool arguments. *(03)*
- [ ] Business rules re-checked inside tools; side effects idempotent. *(03, capstone)*
- [ ] Timeouts on every network call inside tools; long tools honour `cancel_signal`. *(03, 15)*
- [ ] Small tool results; big ones offloaded. *(03, 10)*
- [ ] MCP servers trusted, version-pinned, allow-listed with `tool_filters` and prefixed. *(04)*

## 3. Control and safety

- [ ] Money/deletion/external messages: interventions (`Deny`, `Confirm`) + tool checks. *(09)*
- [ ] Workflow rules enforced with steering, not only the prompt. *(09)*
- [ ] Untrusted text (emails, web, tickets) read by a tool-less agent → typed facts. *(16)*
- [ ] PII redacted before the model, in logs and in traces. *(16, 17)*
- [ ] Guardrail in shadow mode, then enforced, with a pinned version. *(16)*
- [ ] History and memory loaded only from your own storage. *(11, 16)*
- [ ] Security handlers fail closed (`on_error="deny"`); telemetry fails open. *(09)*

## 4. Limits and lifecycle

- [ ] `limits={"turns", "total_tokens"}` on every call. *(15)*
- [ ] A deadline (`cancel_signal` + timer) shorter than the platform timeout. *(15)*
- [ ] Retry strategy tuned to fit inside the deadline. *(15)*
- [ ] `stop_reason` mapped to a small set of API statuses. *(15)*
- [ ] Sub-agents, graphs and swarms have their own limits/timeouts. *(12–14)*
- [ ] `GoalLoop` / Guide loops bounded. *(08, 09)*

## 5. State and data

- [ ] Fresh agent per request (or per conversation with a lock); never shared across users. *(11, 15)*
- [ ] Session ID derived from the authenticated user. *(capstone)*
- [ ] Durable session storage (S3/DynamoDB/AgentCore Memory) with retention and deletion. *(11)*
- [ ] Context management on for long conversations. *(10)*
- [ ] Per-user memory namespaces. *(11)*

## 6. Observability

- [ ] OpenTelemetry tracing exported; `trace_attributes` with session/user IDs. *(17)*
- [ ] One JSON log line per run (IDs, stop reason, tokens, tool counts); no raw content. *(07, 17)*
- [ ] Dashboards + alerts: latency, errors, stop reasons, tokens/cost, tool errors. *(17)*

## 7. Quality

- [ ] Unit tests with a scripted model for tools, hooks, policies, API. *(18)*
- [ ] Eval suite (deterministic + LLM judges) gating every prompt/tool/model change. *(18)*
- [ ] Chaos tests (tool failures) and red-team tests. *(18)*
- [ ] Production failures turned into new eval cases. *(18)*

## 8. Deployment (your platform)

- [ ] Verified authentication (JWT/IAM) in front of the agent; rate limits per user. *(19)*
- [ ] Locked, hash-checked dependencies; non-root container; arm64 for AgentCore. *(19, capstone)*
- [ ] Least-privilege IAM role (only the model ARNs, bucket prefixes and guardrail it uses). *(19)*
- [ ] Secrets from a secret store / AgentCore Identity at runtime. *(19)*
- [ ] Health checks, graceful shutdown, staged rollout, fast rollback. *(19)*
- [ ] Budget alarms on model spend.
