"""Lesson 02 - a Bedrock model configured the way you would run it in production.

Run:  uv run python lessons/02_model_providers/bedrock_production.py
Needs AWS credentials with Bedrock model access (MODEL_PROVIDER does not matter here).

Every argument is explained in this lesson's README ("BedrockModel settings").
"""

from __future__ import annotations

from botocore.config import Config
from strands import Agent
from strands.models import BedrockModel, CacheConfig

from course_common import get_settings, setup_logging, show_result


def production_bedrock_model(model_id: str | None = None) -> BedrockModel:
    settings = get_settings()
    return BedrockModel(
        # --- which model --------------------------------------------------------
        model_id=model_id or settings.model_id or "us.amazon.nova-pro-v1:0",
        region_name=settings.aws_region,
        # --- network: fail fast, retry a little ---------------------------------
        boto_client_config=Config(
            connect_timeout=5,  # seconds to open the connection
            read_timeout=120,  # seconds to wait for data on a long answer
            retries={"max_attempts": 3, "mode": "standard"},  # network/5xx only
            max_pool_connections=50,  # >= number of concurrent agents per process
        ),
        # --- sampling ------------------------------------------------------------
        temperature=0.2,  # low = consistent tool choices
        max_tokens=2048,  # cap ONE reply (cost + latency guard)
        stop_sequences=[],  # optional strings that end generation early
        streaming=True,  # ConverseStream: first words arrive sooner
        # --- cost ----------------------------------------------------------------
        # Cache the stable prefix (system prompt, tools, old messages) so repeated
        # calls are cheaper and faster. Works on models that support prompt caching.
        cache_config=CacheConfig(strategy="auto"),
        # service_tier="flex",  # cheaper/slower batch-like work, where supported
        # --- safety (lesson 16) --------------------------------------------------
        # guardrail_id=settings.bedrock_guardrail_id,
        # guardrail_version=settings.bedrock_guardrail_version,
        # --- model-specific request fields ---------------------------------------
        # additional_request_fields={"reasoningConfig": {...}},  # e.g. reasoning effort
    )


def main() -> None:
    setup_logging()
    agent = Agent(
        model=production_bedrock_model(),
        system_prompt="You are a concise assistant.",
        callback_handler=None,
    )
    result = agent("Give me three tips for writing good tool docstrings.")
    print(result)
    show_result(result)


if __name__ == "__main__":
    main()
