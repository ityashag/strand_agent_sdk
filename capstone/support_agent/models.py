"""Model construction: explicit settings, timeouts, small retries, optional fallback (lesson 02)."""

from __future__ import annotations

from typing import Any

from strands.models import ModelRouter
from strands.models.model import Model

from support_agent.config import AppSettings


def _one_model(settings: AppSettings, model_id: str) -> Model:
    if settings.model_provider == "bedrock":
        from botocore.config import Config
        from strands.models import BedrockModel, CacheConfig

        extra: dict[str, Any] = {}
        if settings.guardrail_id:
            extra = {
                "guardrail_id": settings.guardrail_id,
                "guardrail_version": settings.guardrail_version,
                "guardrail_latest_message": True,
            }
        return BedrockModel(
            model_id=model_id,
            region_name=settings.aws_region,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            cache_config=CacheConfig(strategy="auto"),
            boto_client_config=Config(
                connect_timeout=5,
                read_timeout=120,
                retries={"max_attempts": 3, "mode": "standard"},
                max_pool_connections=50,
            ),
            **extra,
        )
    if settings.model_provider == "openai":
        from strands.models.openai import OpenAIModel

        return OpenAIModel(
            client_args={"timeout": 120, "max_retries": 2},
            model_id=model_id,
            params={"temperature": settings.temperature, "max_tokens": settings.max_tokens},
        )
    from strands.models.ollama import OllamaModel

    return OllamaModel(
        host=settings.ollama_host,
        model_id=model_id,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        options={"num_ctx": 16384},
    )


def build_model(settings: AppSettings) -> Model | ModelRouter:
    primary = _one_model(settings, settings.model_id)
    if not settings.fallback_model_id:
        return primary
    return ModelRouter(
        models=[primary, _one_model(settings, settings.fallback_model_id)], max_switches=1
    )
