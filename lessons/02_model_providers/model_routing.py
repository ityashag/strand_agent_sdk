"""Lesson 02 - model routing: a backup model when the main one fails.

Run:  uv run python lessons/02_model_providers/model_routing.py

ModelRouter is passed as the agent's model. It tries candidates in order; when a model
call fails with an error the retry strategy does not handle, it switches to the next one.
Throttling is first retried on the SAME model by the retry strategy (lesson 15).
"""

from __future__ import annotations

from strands import Agent
from strands.models import ModelRouter
from strands.models.model import Model

from course_common import build_model, get_settings, setup_logging, show_result


def build_router(primary: Model | None = None, backup: Model | None = None) -> ModelRouter:
    settings = get_settings()
    return ModelRouter(
        models=[
            primary or build_model(),  # first = default candidate
            backup or build_model(model_id=settings.small_model_id or None),
        ],
        # At most one successful switch per invocation. Without a cap the strategy
        # decides when to stop (it never re-tries a model in the same failure round).
        max_switches=1,
    )


def build_agent(router: ModelRouter | None = None) -> Agent:
    return Agent(model=router or build_router(), callback_handler=None)


def main() -> None:
    setup_logging()
    agent = build_agent()
    result = agent("Summarize the trade-offs of active-active deployment in 3 bullets.")
    print(result)
    show_result(result)


if __name__ == "__main__":
    main()
