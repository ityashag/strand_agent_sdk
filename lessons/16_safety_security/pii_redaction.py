"""Lesson 16 - PII redaction before text reaches the model, logs and traces.

Run:  uv run python lessons/16_safety_security/pii_redaction.py

Where PII can leak in an agent:
  user input -> model provider -> traces/logs -> session storage -> tool results -> answers
This example redacts the user's message BEFORE the first model call, so the provider,
traces and stored history never see it. (Lesson 09 redacts tool results the same way.)

Regexes are a demo. In production use a real PII detector (Amazon Comprehend, Bedrock
Guardrails sensitive-information filters, Microsoft Presidio) and test it.
"""

from __future__ import annotations

import re
from typing import Any

from strands import Agent
from strands.hooks import BeforeInvocationEvent
from strands.interventions import InterventionHandler, OnError, Proceed, Transform
from strands.models.model import Model

from course_common import build_model, setup_logging

PATTERNS: dict[str, re.Pattern[str]] = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "CARD": re.compile(r"\b(?:\d[ -]?){12,15}\d\b"),
    "PHONE": re.compile(r"\+?\d{1,3}[ -]?\d{3,5}[ -]?\d{4,6}\b"),
    "AADHAAR": re.compile(r"\b\d{4} \d{4} \d{4}\b"),
}


def redact(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for label, pattern in PATTERNS.items():
        text, n = pattern.subn(f"[{label}]", text)
        if n:
            counts[label] = n
    return text, counts


class RedactUserInput(InterventionHandler):
    name = "redact-user-input"

    def __init__(self) -> None:
        self.found: list[dict[str, int]] = []

    @property
    def on_error(self) -> OnError:
        return "deny"  # if redaction breaks, do not send unredacted text (fail closed)

    def before_invocation(self, event: BeforeInvocationEvent, **kwargs: Any) -> Any:
        if not event.messages:
            return Proceed()

        def apply(e: Any) -> None:
            for message in e.messages or []:
                if message.get("role") != "user":
                    continue
                for block in message.get("content", []):
                    if "text" in block:
                        block["text"], counts = redact(block["text"])
                        if counts:
                            self.found.append(counts)

        return Transform(apply=apply)


def build_agent(model: Model | None = None, redactor: RedactUserInput | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        interventions=[redactor or RedactUserInput()],
        system_prompt="You are a support agent. Never ask for full card numbers.",
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    redactor = RedactUserInput()
    agent = build_agent(redactor=redactor)
    agent("My card 4111 1111 1111 1111 was charged twice, email me at asha@example.com")
    print("stored history:", agent.messages[0]["content"])
    print("redactions:", redactor.found)


if __name__ == "__main__":
    main()
