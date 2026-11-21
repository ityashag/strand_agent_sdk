"""Lesson 01 - the smallest real agent.

Run:  uv run python lessons/01_agent_loop/simple_agent.py

This is already a full agent loop. It has no tools, so the loop runs once: the model
answers and stops with stop_reason "end_turn".
"""

from __future__ import annotations

from strands import Agent
from strands.models.model import Model

from course_common import build_model, setup_logging, show_result

SYSTEM_PROMPT = """You are a senior backend engineer who explains things simply.
Answer in at most 5 short bullet points."""


def build_agent(model: Model | None = None) -> Agent:
    """Agent factory. Production code builds agents in one place like this."""
    return Agent(
        # Always pass the model explicitly. Relying on the SDK default model means
        # an SDK upgrade can silently change which model (and price) you use.
        model=model or build_model(),
        system_prompt=SYSTEM_PROMPT,
        # name/description identify the agent in traces and in multi-agent systems.
        name="explainer",
        description="Explains backend engineering concepts in plain words.",
        # The default callback handler streams text to stdout. Nice in a terminal,
        # wrong on a server. Lesson 06 covers this; here we keep the default.
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    result = agent("What are the key differences between REST and GraphQL APIs?")
    # result is an AgentResult. str(result) is the final text.
    show_result(result, agent.messages)


if __name__ == "__main__":
    main()
