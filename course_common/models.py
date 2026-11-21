"""One place that turns settings into a Strands model object.

Every lesson calls ``build_model()``. Change ``MODEL_PROVIDER`` / ``MODEL_ID`` in `.env`
and every lesson switches provider; the agent code never changes. That is the whole point
of lesson 02: the model is a plug-in part of the harness.
"""

from __future__ import annotations

from typing import Any

from strands.models.model import Model

from course_common.config import CourseSettings, get_settings
from course_common.fake_model import ScriptedModel


def build_model(
    settings: CourseSettings | None = None,
    *,
    model_id: str | None = None,
    small: bool = False,
    **overrides: Any,
) -> Model:
    """Build the configured model.

    Args:
        settings: Settings to use (defaults to the environment).
        model_id: Force a specific model ID for this call.
        small: Use ``SMALL_MODEL_ID`` (for judges, summaries, classifiers).
        **overrides: Extra provider config, e.g. ``temperature=0`` for a classifier.
    """
    s = settings or get_settings()
    chosen_id = model_id or (s.small_model_id if small and s.small_model_id else s.model_id)

    if s.model_provider == "fake":
        return ScriptedModel(model_id=chosen_id or "scripted-model")
    if s.model_provider == "bedrock":
        return _bedrock(s, chosen_id, overrides)
    if s.model_provider == "openai":
        return _openai(s, chosen_id, overrides)
    if s.model_provider == "anthropic":
        return _anthropic(s, chosen_id, overrides)
    if s.model_provider == "ollama":
        return _ollama(s, chosen_id, overrides)
    raise ValueError(f"Unknown MODEL_PROVIDER: {s.model_provider}")


def _sampling(s: CourseSettings, overrides: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {"max_tokens": overrides.pop("max_tokens", s.max_tokens)}
    temperature = overrides.pop("temperature", s.temperature)
    if temperature is not None:
        params["temperature"] = temperature
    return params


def _bedrock(s: CourseSettings, model_id: str, overrides: dict[str, Any]) -> Model:
    from botocore.config import Config
    from strands.models import BedrockModel

    # Two retry layers exist. botocore retries network/5xx errors on ONE request; the
    # Strands ModelRetryStrategy (lesson 15) retries throttling for the whole model call.
    # Keep the botocore layer small, otherwise retries multiply (3 x 6 = 18 attempts).
    client_config = Config(
        connect_timeout=s.connect_timeout,
        read_timeout=s.read_timeout,
        retries={"max_attempts": s.client_max_retries + 1, "mode": "standard"},
        user_agent_extra="strands-course",
    )
    config: dict[str, Any] = {**_sampling(s, overrides), **overrides}
    if model_id:
        config["model_id"] = model_id
    if s.bedrock_guardrail_id:
        config.setdefault("guardrail_id", s.bedrock_guardrail_id)
        config.setdefault("guardrail_version", s.bedrock_guardrail_version)
    return BedrockModel(region_name=s.aws_region, boto_client_config=client_config, **config)


def _openai(s: CourseSettings, model_id: str, overrides: dict[str, Any]) -> Model:
    from strands.models.openai import OpenAIModel

    if not model_id:
        raise ValueError("Set MODEL_ID for the openai provider (for example gpt-4o).")
    return OpenAIModel(
        # The API key is read from OPENAI_API_KEY by the OpenAI client itself.
        client_args={"timeout": s.read_timeout, "max_retries": s.client_max_retries},
        model_id=model_id,
        params={**_sampling(s, overrides), **overrides},
    )


def _anthropic(s: CourseSettings, model_id: str, overrides: dict[str, Any]) -> Model:
    from strands.models.anthropic import AnthropicModel

    if not model_id:
        raise ValueError("Set MODEL_ID for the anthropic provider.")
    sampling = _sampling(s, overrides)
    return AnthropicModel(
        # The API key is read from ANTHROPIC_API_KEY by the Anthropic client itself.
        client_args={"timeout": s.read_timeout, "max_retries": s.client_max_retries},
        model_id=model_id,
        max_tokens=sampling.pop("max_tokens"),
        params={**sampling, **overrides},
    )


def _ollama(s: CourseSettings, model_id: str, overrides: dict[str, Any]) -> Model:
    from strands.models.ollama import OllamaModel

    if not model_id:
        raise ValueError("Set MODEL_ID for the ollama provider (for example qwen3:8b).")
    return OllamaModel(
        host=s.ollama_host,
        model_id=model_id,
        keep_alive="10m",  # keep the model loaded between calls
        **_sampling(s, overrides),
        **overrides,
    )
