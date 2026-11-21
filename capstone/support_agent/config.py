"""All service settings in one typed object, read from SUPPORT_* environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUPPORT_", env_file=".env", extra="ignore")

    # --- model (lesson 02) ----------------------------------------------------------
    model_provider: Literal["bedrock", "openai", "ollama"] = "bedrock"
    model_id: str = "us.amazon.nova-pro-v1:0"
    fallback_model_id: str = ""  # same provider; used when the main model fails
    aws_region: str = "us-east-1"
    temperature: float = Field(default=0.2, ge=0, le=1)
    max_tokens: int = Field(default=2048, gt=0)
    ollama_host: str = "http://localhost:11434"

    # --- safety (lesson 16) ---------------------------------------------------------
    guardrail_id: str = ""
    guardrail_version: str = ""
    max_message_chars: int = 4000

    # --- refund policy, enforced in code (lesson 09) --------------------------------
    refund_auto_approve_limit: float = 50.0  # above this a supervisor must approve
    refund_hard_limit: float = 500.0  # above this: never, escalate instead

    # --- limits per request (lesson 15) ---------------------------------------------
    max_turns: int = 8
    max_total_tokens: int = 40_000
    deadline_seconds: float = 60.0

    # --- sessions (lesson 11) -------------------------------------------------------
    session_bucket: str = ""  # S3 bucket in the cloud; empty -> local files
    session_prefix: str = "support-sessions/"
    session_dir: str = "./sessions"

    # --- logs (lesson 17) -----------------------------------------------------------
    json_logs: bool = True
    log_level: str = "INFO"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
