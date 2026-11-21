"""Lesson 16 - Bedrock Guardrails: enforce mode and shadow (notify-only) mode.

Run:  uv run python lessons/16_safety_security/guardrails.py
Needs AWS credentials and a guardrail: create one in the Bedrock console, then set
BEDROCK_GUARDRAIL_ID / BEDROCK_GUARDRAIL_VERSION in .env.

Enforce mode: the guardrail blocks input/output; stop_reason == "guardrail_intervened".
Shadow mode : the guardrail only LOGS what it would block. Run it for a week on real traffic,
              tune the policy, then switch to enforce. (No surprise refusals on launch day.)
"""

from __future__ import annotations

import logging
from typing import Any

from strands import Agent
from strands.hooks import AfterInvocationEvent, BeforeInvocationEvent, HookProvider, HookRegistry
from strands.models import BedrockModel

from course_common import get_settings, setup_logging

log = logging.getLogger("guardrail.shadow")


def enforced_guardrail_model() -> BedrockModel:
    settings = get_settings()
    return BedrockModel(
        model_id=settings.model_id or "us.amazon.nova-pro-v1:0",
        region_name=settings.aws_region,
        guardrail_id=settings.bedrock_guardrail_id,
        guardrail_version=settings.bedrock_guardrail_version,  # pin a number in prod, not DRAFT
        guardrail_trace="enabled",  # see which policy fired (debugging)
        guardrail_redact_input=True,  # replace blocked user text in history...
        guardrail_redact_input_message="[User input redacted by guardrail]",
        guardrail_redact_output=False,
        guardrail_latest_message=True,  # only check the newest user message (cheaper)
    )


class ShadowGuardrail(HookProvider):
    """Call the ApplyGuardrail API on input and output, but never block. Log only."""

    def __init__(
        self, guardrail_id: str, version: str, client: Any = None, region: str = "us-east-1"
    ) -> None:
        import boto3

        self.guardrail_id = guardrail_id
        self.version = version
        self.client = client or boto3.client("bedrock-runtime", region_name=region)
        self.would_block: list[dict[str, Any]] = []

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeInvocationEvent, self.check_input)
        registry.add_callback(AfterInvocationEvent, self.check_output)

    def _evaluate(self, text: str, source: str) -> None:
        if not text:
            return
        try:
            response = self.client.apply_guardrail(
                guardrailIdentifier=self.guardrail_id,
                guardrailVersion=self.version,
                source=source,  # "INPUT" or "OUTPUT"
                content=[{"text": {"text": text}}],
            )
        except Exception:  # shadow mode must never break the agent
            log.warning("shadow guardrail call failed", exc_info=True)
            return
        if response.get("action") == "GUARDRAIL_INTERVENED":
            record = {"source": source, "assessments": response.get("assessments", [])}
            self.would_block.append(record)
            # Log the policy that fired, NOT the user's text (it may be sensitive).
            log.warning("guardrail would block", extra={"fields": {"source": source}})

    def check_input(self, event: BeforeInvocationEvent) -> None:
        messages = event.messages or []
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if last_user:
            self._evaluate(" ".join(b.get("text", "") for b in last_user["content"]), "INPUT")

    def check_output(self, event: AfterInvocationEvent) -> None:
        if event.result is not None:
            self._evaluate(str(event.result), "OUTPUT")


def main() -> None:
    setup_logging()
    settings = get_settings()
    if not settings.bedrock_guardrail_id:
        print("Set BEDROCK_GUARDRAIL_ID in .env to run this demo.")
        return
    agent = Agent(model=enforced_guardrail_model(), system_prompt="You are a banking assistant.")
    result = agent("Tell me how to launder money.")
    print("stop_reason:", result.stop_reason)  # guardrail_intervened when blocked


if __name__ == "__main__":
    main()
