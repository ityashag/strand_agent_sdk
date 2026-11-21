"""Lesson 08 - GoalLoop: the agent is not done until a check says it is done.

Run:  uv run python lessons/08_plugins_skills/goal_loop.py

GoalLoop runs your validator after each answer. If the check fails, the feedback is sent
back as a new user message and the agent tries again, until it passes or the budget ends.

The validator can be:
  - a Python function (real checks: tests pass, JSON parses, fields present)  <- shown here
  - a sentence, e.g. GoalLoop(goal="The answer cites at least two sources"),
    judged by a second model (pass judge={"model": small_model} to choose which one)
"""

from __future__ import annotations

import json
from typing import Any

from strands import Agent
from strands.models.model import Model
from strands.types.content import Message
from strands.vended_plugins.goal import GoalLoop

from course_common import build_model, setup_logging

REQUIRED_KEYS = {"title", "severity", "steps_to_reproduce"}


def valid_bug_report(response: Message, agent: Agent, **kwargs: Any) -> dict[str, Any]:
    """Pass only if the answer is a JSON object with the required keys."""
    text = "".join(block.get("text", "") for block in response.get("content", []))
    try:
        data = json.loads(text.strip().removeprefix("```json").removesuffix("```"))
    except json.JSONDecodeError as error:
        return {"passed": False, "feedback": f"Reply with JSON only. Parse error: {error}"}
    if not isinstance(data, dict):
        return {"passed": False, "feedback": "Reply with a JSON object, not a list."}
    missing = REQUIRED_KEYS - set(data)
    if missing:
        return {"passed": False, "feedback": f"Missing keys: {sorted(missing)}"}
    if data["severity"] not in {"low", "medium", "high"}:
        return {"passed": False, "feedback": "severity must be low, medium or high"}
    return {"passed": True}


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        system_prompt="Turn user complaints into bug reports as JSON with title, severity, steps_to_reproduce.",
        plugins=[
            GoalLoop(
                goal=valid_bug_report,
                # ALWAYS bound it in production, or a model that cannot pass loops forever.
                max_attempts=3,
                timeout=120,  # seconds for the whole goal run
            )
        ],
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    result = agent("The app crashes when I upload a PNG bigger than 10MB on Android.")
    print(result)


if __name__ == "__main__":
    main()
