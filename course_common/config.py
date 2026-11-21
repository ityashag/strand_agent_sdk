"""Typed settings for every lesson, read from environment variables or a `.env` file.

Production rule: configuration comes from the environment, never from code. The same code
then runs on your laptop (Ollama, `.env`), in CI (`MODEL_PROVIDER=fake`) and in the cloud
(Bedrock, values injected by the platform). Secrets such as `OPENAI_API_KEY` are NOT fields
here: the provider SDKs read them from the environment themselves, so they never end up in
a settings object that might be logged.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Provider = Literal["bedrock", "openai", "anthropic", "ollama", "fake"]


class CourseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Which model provider to use. "fake" runs offline with a scripted model.
    model_provider: Provider = "bedrock"
    # Model ID for that provider. Empty means "use the provider's default" (Bedrock only).
    model_id: str = ""
    # A cheaper/faster model for helpers: summaries, judges, classifiers.
    small_model_id: str = ""

    # Sampling. None means "do not send it" (some reasoning models reject temperature).
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, gt=0)

    # AWS / Bedrock
    aws_region: str = "us-east-1"
    bedrock_guardrail_id: str = ""
    bedrock_guardrail_version: str = "DRAFT"

    # Network behaviour of the provider client (seconds / attempts).
    connect_timeout: float = 10.0
    read_timeout: float = 120.0
    client_max_retries: int = 2

    # Ollama
    ollama_host: str = "http://localhost:11434"

    # Logging: DEBUG shows Strands internals, INFO is right for most services.
    log_level: str = "INFO"


@lru_cache
def get_settings() -> CourseSettings:
    """Load settings once per process (cheap to call everywhere)."""
    return CourseSettings()
