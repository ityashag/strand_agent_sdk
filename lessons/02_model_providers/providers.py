"""Lesson 02 - same agent, different model providers.

Run:  uv run python lessons/02_model_providers/providers.py            # uses MODEL_PROVIDER from .env
      uv run python lessons/02_model_providers/providers.py ollama     # force one provider

The agent code below never changes. Only the model object changes. Each builder shows the
settings that matter for that provider; course_common/models.py is the version all
lessons use.
"""

from __future__ import annotations

import os
import sys

from strands import Agent
from strands.models.model import Model

from course_common import build_model, get_settings, setup_logging, show_result


def bedrock() -> Model:
    from strands.models import BedrockModel

    # Auth: your normal AWS credentials (profile, SSO, or an IAM role in the cloud).
    # Model IDs with a "us." / "eu." / "global." prefix are inference profiles: AWS
    # routes the call to a region with capacity. Prefer them in production.
    return BedrockModel(
        model_id=get_settings().model_id or "us.amazon.nova-pro-v1:0",
        region_name=get_settings().aws_region,
        temperature=0.3,
        max_tokens=1024,
    )


def openai() -> Model:
    from strands.models.openai import OpenAIModel

    # Auth: OPENAI_API_KEY in the environment (the openai client reads it).
    # client_args go to openai.AsyncOpenAI(...): timeout, max_retries, base_url (for
    # OpenAI-compatible servers such as vLLM or LM Studio), organization...
    return OpenAIModel(
        client_args={"timeout": 60, "max_retries": 2},
        model_id=get_settings().model_id or "gpt-4o",
        params={"max_tokens": 1024, "temperature": 0.3},  # sent as-is to the API
    )


def anthropic() -> Model:
    from strands.models.anthropic import AnthropicModel

    # Auth: ANTHROPIC_API_KEY in the environment. max_tokens is required by this API.
    return AnthropicModel(
        client_args={"timeout": 60, "max_retries": 2},
        model_id=get_settings().model_id or "claude-sonnet-4-5",
        max_tokens=1024,
        params={"temperature": 0.3},
    )


def ollama() -> Model:
    from strands.models.ollama import OllamaModel

    # Auth: none. Runs on your machine:  ollama serve  &&  ollama pull qwen3:8b
    # Pick a model trained for tool calling (qwen3, llama3.1+, mistral-nemo...).
    return OllamaModel(
        host=get_settings().ollama_host,
        model_id=get_settings().model_id or "qwen3:8b",
        temperature=0.3,
        max_tokens=1024,
        keep_alive="10m",
        options={"num_ctx": 16384},  # Ollama's context window; the default is small
    )


BUILDERS = {"bedrock": bedrock, "openai": openai, "anthropic": anthropic, "ollama": ollama}


def build_agent(model: Model | None = None) -> Agent:
    # Identical for every provider: tools, prompt and orchestration do not change.
    return Agent(
        model=model or build_model(),
        system_prompt="Explain things in one short paragraph.",
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    choice = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MODEL_PROVIDER", "")
    model = BUILDERS[choice]() if choice in BUILDERS else build_model()
    print(f"provider={type(model).__name__} config={model.get_config()}")
    agent = build_agent(model)
    result = agent("Explain the agent loop in one paragraph.")
    print(result)
    show_result(result)


if __name__ == "__main__":
    main()
