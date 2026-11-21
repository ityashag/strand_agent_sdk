# Lesson 19 — Deploying agents to the cloud

## In simple words

A Strands agent is just Python. To put it in production you wrap it in an **entrypoint** (an HTTP
handler or a Lambda handler), package it (usually a container), and run it on a platform that scales it.
The agent code doesn't change.

## Files

| File | What it shows |
|------|---------------|
| [agentcore_app.py](agentcore_app.py) | `BedrockAgentCoreApp` entrypoint: input validation, session from the runtime header, S3-backed sessions, limits, deadline, streamed events. |
| [lambda_handler.py](lambda_handler.py) | AWS Lambda handler: model reused across warm starts, agent per invocation, deadline from Lambda's remaining time. |
| [Dockerfile](Dockerfile) | arm64-ready image with uv, non-root user, port 8080. |
| [../06_streaming_callbacks/streaming_api.py](../06_streaming_callbacks/streaming_api.py) | FastAPI + SSE (for ECS/Fargate/EKS/App Runner). |
| [../../capstone](../../capstone) | The full production service. |

```bash
uv run python lessons/19_deployment/agentcore_app.py      # local server on :8080
curl -N localhost:8080/invocations -H 'content-type: application/json' \
  -H 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: 0f8c6a3e-demo-session-0000000000001' \
  -d '{"prompt": "I am C-1001. What did I order?"}'
```

## Where to run it

| Platform | Good for | Streaming | Notes |
|----------|----------|-----------|-------|
| **Bedrock AgentCore Runtime** | Agents on AWS, per-session isolation | yes | microVM per session, long runs (hours), built-in tracing, Memory, Gateway (tools as MCP), Identity (OAuth/IAM) |
| AWS Lambda | short requests, batch jobs, event-driven | limited | 15-minute cap, cold starts; agent per invocation |
| ECS Fargate / App Runner | always-on HTTP APIs | yes | FastAPI + SSE behind a load balancer |
| EKS / EC2 | full control, high volume | yes | you run scaling and patching |
| Docker anywhere | local, other clouds | yes | same image everywhere |

## AgentCore Runtime in 5 steps

The official course uses the AgentCore CLI:

```bash
npm install -g @aws/agentcore
agentcore create --name SupportAgent --project-name StrandsCourse --framework Strands \
  --model-provider Bedrock --language Python --memory none
# copy your entrypoint + code into the generated app folder, then:
agentcore deploy
agentcore invoke --session-id "$(python3 -c 'import uuid; print(uuid.uuid4())')" '{"prompt": "hi"}'
```

| AgentCore piece | What it gives you |
|-----------------|-------------------|
| Runtime | runs the container; one isolated microVM per session; `/invocations` + `/ping` contract on port 8080 |
| Memory | `AgentCoreMemorySessionManager` from `bedrock_agentcore.memory.integrations.strands`: conversation persistence + long-term memory strategies (facts, preferences) |
| Gateway | turn APIs/Lambdas into MCP tools with auth; connect with `MCPClient(url=...)` (lesson 04) |
| Identity | inbound auth (IAM / OAuth JWT) and outbound credentials for tools (token vault) |
| Observability | traces and metrics in CloudWatch GenAI observability |
| Policy | Cedar policies deciding which tool calls are allowed |

## Configuration the container needs

| Variable | Example | Why |
|----------|---------|-----|
| `MODEL_PROVIDER`, `MODEL_ID`, `AWS_REGION` | `bedrock`, `us.amazon.nova-pro-v1:0`, `us-east-1` | which model |
| `SESSION_BUCKET` | `my-agent-sessions` | durable sessions (S3) |
| `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT` | `support-agent` | tracing (lesson 17) |
| `LOG_LEVEL` | `INFO` | logs |
| Secrets (API keys) | from Secrets Manager / AgentCore Identity at runtime | **never** baked into the image or env files in git |

## IAM: least privilege for the runtime role

- `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` on **only** the model / inference profile ARNs you use.
- `bedrock:ApplyGuardrail` on your guardrail (if used).
- `s3:GetObject`, `s3:PutObject` on `arn:aws:s3:::<bucket>/sessions/*` only.
- Logs/X-Ray permissions for telemetry. Nothing else.

## Production checklist for deployment

- [ ] **Session ID from your authenticated backend**, never from the end user. One session per user conversation.
- [ ] Input validation at the edge (size, type), rate limits per user/tenant (API Gateway / WAF).
- [ ] Limits + deadline on every request (lesson 15); deadline shorter than the platform timeout.
- [ ] Durable sessions/memory (S3, DynamoDB, AgentCore Memory) with retention rules.
- [ ] Image: pinned base and dependencies (`uv.lock`), non-root user, arm64 for AgentCore, no secrets inside.
- [ ] Health check (`/ping` or `/healthz`) and graceful shutdown.
- [ ] Tracing + JSON logs + dashboards and alerts (lesson 17).
- [ ] Evals in the CI pipeline gate the deploy (lesson 18); canary or staged rollout; quick rollback.
- [ ] Cost guardrails: budgets/alarms on model spend.

## Try it

1. Run `agentcore_app.py`, send two requests with the same session header, and check the second remembers the first.
2. Build the image: `docker build --platform linux/arm64 -f lessons/19_deployment/Dockerfile -t strands-lesson19 .`
3. Point `SESSION_BUCKET` at a real bucket and watch session snapshots appear under `sessions/`.
