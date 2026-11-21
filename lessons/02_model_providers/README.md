# Lesson 02 — Switching model providers

## In simple words

The model is a **plug-in part** of your agent. Strands talks to every provider through one
interface, so your tools, prompt and logic stay the same when you change from Bedrock to OpenAI
to a free local model. You only change the model object.

Choosing a model is an **architecture decision**: models differ in quality, price, speed, context
size, and how well they call tools. Big systems use several:

| Job | Model to use |
|-----|--------------|
| Orchestrator, hard reasoning | strongest model |
| Specialists doing focused work | mid-size model |
| Classifiers, routers, summaries, guards | small, fast, cheap model |
| Evaluation / judging | a **different** provider than the one being judged (avoids same-model bias) |

## Files

| File | What it shows |
|------|---------------|
| [providers.py](providers.py) | Bedrock, OpenAI, Anthropic and Ollama builders; the agent code never changes. |
| [bedrock_production.py](bedrock_production.py) | A Bedrock model with every production setting filled in. |
| [model_routing.py](model_routing.py) | `ModelRouter`: fall back to a backup model when the main one fails. |
| [../../course_common/models.py](../../course_common/models.py) | The factory every lesson uses (`MODEL_PROVIDER` in `.env`). |

```bash
uv run python lessons/02_model_providers/providers.py ollama
```

## Providers

| Provider | Install extra | Auth | Class |
|----------|---------------|------|-------|
| Amazon Bedrock (default) | – | AWS credentials (profile, SSO, IAM role) | `strands.models.BedrockModel` |
| OpenAI (and OpenAI-compatible servers) | `[openai]` | `OPENAI_API_KEY` | `strands.models.openai.OpenAIModel` |
| OpenAI Responses API | `[openai]` | `OPENAI_API_KEY` | `strands.models.openai_responses.OpenAIResponsesModel` |
| Anthropic | `[anthropic]` | `ANTHROPIC_API_KEY` | `strands.models.anthropic.AnthropicModel` |
| Google Gemini | `[gemini]` | `GOOGLE_API_KEY` | `strands.models.gemini.GeminiModel` |
| Ollama (local) | `[ollama]` | none | `strands.models.ollama.OllamaModel` |
| LiteLLM (100+ providers) | `[litellm]` | per provider | `strands.models.litellm.LiteLLMModel` |
| Mistral, Writer, LlamaAPI, llama.cpp, SageMaker | `[mistral]` etc. | per provider | `strands.models.<name>` |
| Your own | – | – | subclass `strands.models.model.Model` (see `course_common/fake_model.py`) |

A plain string also works: `Agent(model="us.amazon.nova-pro-v1:0")` means "Bedrock with this model ID".

## `BedrockModel` settings

| Setting | What it does | Default | Production advice |
|---------|--------------|---------|-------------------|
| `model_id` | Which model. `us.`/`eu.`/`global.` prefixes are **inference profiles** that route to a region with capacity. | `global.anthropic.claude-sonnet-4-6` | Set it. Use an inference profile (or an application inference profile ARN for cost tracking). |
| `region_name` | AWS region for the client. | session region, `AWS_REGION`, else `us-west-2` | Set it explicitly. |
| `boto_session` | A ready `boto3.Session` (profile, assumed role). | new session | Pass one when you assume a role per tenant. |
| `boto_client_config` | botocore `Config`: timeouts, retries, connection pool. | botocore defaults | `connect_timeout=5`, `read_timeout=120`, `retries={"max_attempts": 3, "mode": "standard"}`, `max_pool_connections` ≥ concurrent agents. |
| `temperature` | Randomness. 0 = most repeatable. | model default | 0–0.3 for tool use and extraction; higher for creative text. |
| `top_p` | Alternative to temperature. | model default | Set temperature **or** top_p, not both (some models reject both). |
| `max_tokens` | Max length of **one** reply. | the model's max output | Set it. It caps cost and latency. Too low → `MaxTokensReachedException`. |
| `stop_sequences` | Strings that end the reply early. | none | Rarely needed. |
| `streaming` | Use ConverseStream (`True`) or Converse (`False`). | `True` | Keep `True`; turn off only for models without streaming tool use. |
| `cache_config` | Prompt caching: `CacheConfig(strategy="auto")` caches the stable prefix (system prompt, tools, history). | off | Turn on for long system prompts / many tools: cheaper and faster on repeated calls. |
| `service_tier` | `"default"`, `"priority"` (faster, costs more), `"flex"` (cheaper, slower). | default | `flex` for background jobs where supported. |
| `guardrail_id`, `guardrail_version`, `guardrail_trace` | Bedrock Guardrails on input and output. | off | Lesson 16. |
| `guardrail_redact_input` / `_output` (+ `_message`) | Replace blocked text in history so the next turn is not blocked again. | input `True`, output `False` | Keep input redaction on. |
| `guardrail_latest_message` | Send only the newest user message to the guardrail. | `False` | `True` saves guardrail cost on long chats. |
| `additional_request_fields` | Model-specific fields (e.g. reasoning/thinking settings). | none | Use for reasoning effort on models that support it. |
| `strict_tools` | Constrained decoding for tool inputs (schema must use supported JSON Schema features). | `False` | Turn on when tool arguments must always validate. |
| `include_tool_result_status` | Send `status` on tool results. | `"auto"` | Leave on `auto`. |
| `use_native_token_count` | Use Bedrock's CountTokens API instead of a local estimate. | `False` | `True` if you budget tokens precisely. |
| `context_window_limit` | Tell Strands the window size (used by context management). | from model info | Set it for models Strands does not know. |

### Two retry layers (common mistake)

```
botocore retries  (one HTTP request, network / 5xx)      -> keep small: 3 attempts
ModelRetryStrategy (whole model call, throttling)         -> lesson 15, default 6 attempts
```

They multiply. 6 × 6 = 36 attempts can turn one slow minute into a 20-minute hang. Keep botocore small.

## Other providers' key settings

| Provider | Setting | Meaning |
|----------|---------|---------|
| OpenAI | `client_args` | Passed to `AsyncOpenAI(...)`: `timeout`, `max_retries`, `base_url` (vLLM, LM Studio, Azure-style gateways). |
| OpenAI | `params` | Sent as-is in every request: `max_tokens` / `max_completion_tokens`, `temperature`, `reasoning_effort`... |
| Anthropic | `max_tokens` | **Required.** |
| Anthropic | `params` | `temperature`, `thinking`, etc. |
| Ollama | `host`, `keep_alive` | Server URL; how long the model stays loaded (avoid reload delays). |
| Ollama | `options={"num_ctx": 16384}` | The context window. Ollama's default is small, so long tool results get cut silently. |
| all | `cache_config`, `context_window_limit` | Same meaning as Bedrock where supported. |

## Model routing and fallback

`ModelRouter` is used **as the model**:

```python
from strands.models import ModelRouter, RoutingCandidate, ClassifierStrategy

router = ModelRouter(models=[primary, backup], max_switches=1)  # fallback on failure
agent = Agent(model=router)
```

| Strategy | Use it when |
|----------|-------------|
| `FallbackStrategy` (default) | You want a backup when the main model errors. It also learns which model is healthier. |
| `ClassifierStrategy(classifier_model, routing_policy=...)` | Cheap requests should go to a cheap model and hard ones to a strong model. Costs one extra small call. |
| Your own `RoutingStrategy` | Rules like "tenant X always uses model Y". |

Every candidate must be **stateless** (history lives in the agent). Keep secrets out of candidate
descriptions/metadata: the classifier sends them to a model.

## Production notes

- **Pin the model ID** in config, never rely on the SDK default.
- **Set `max_tokens` and timeouts** on every model. Unbounded = unbounded cost and hangs.
- **Prompt caching** is often the single biggest cost cut for agents with long system prompts and many tools.
- **Low temperature for agents.** Tool choice should be boring and repeatable.
- **Check tool-calling quality** before choosing a model. Small local models often call tools badly.
- **Keep a fallback model** from a different provider or region for outages.
- **Use cheap models for helper jobs** (summaries in lesson 10, judges in lesson 18, routers here).

## Try it

1. Run `providers.py` with two providers and compare answers and token counts.
2. Set `MAX_TOKENS=20` in `.env` and run lesson 01. Which exception or stop reason do you get?
3. Read `test_router_falls_back_to_backup_model` in [tests/test_01_02_basics.py](../../tests/test_01_02_basics.py): it breaks the main model on purpose and checks that the backup answers.
