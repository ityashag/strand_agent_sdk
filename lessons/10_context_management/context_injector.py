"""Lesson 10 - ContextInjector: add fresh facts to ONE model call without storing them.

Run:  uv run python lessons/10_context_management/context_injector.py

Good for facts the model should always have but that do not belong in saved history:
the current time, the user's plan, feature flags, a retrieval result for this question.
The injected text is added to the latest user message for that call. In agent.messages it
is kept only as a marked {"injected": ...} block, and old injections are NOT re-sent on
later calls, so they do not pile up turn after turn.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from strands import Agent
from strands.injection.types import InjectionContext
from strands.models.model import Model
from strands.vended_plugins.context_injector import ContextInjector

from course_common import build_model, setup_logging


def now_block(context: InjectionContext) -> str:
    return f"<now>{datetime.now(UTC).isoformat(timespec='minutes')}</now>"


def profile_block(context: InjectionContext) -> str | None:
    # agent.state is set by YOUR app (never by the model). Escape anything that came from
    # users, so it cannot close the tag and inject instructions.
    profile = context.state.get("profile")
    if not profile:
        return None  # nothing to inject this time
    return f"<user_profile plan='{escape(profile['plan'])}' locale='{escape(profile['locale'])}'/>"


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        system_prompt="You are a billing assistant. Use <now> for dates and <user_profile> for plan facts.",
        state={"profile": {"plan": "pro", "locale": "en-IN"}},
        plugins=[
            # trigger="userTurn" (default): only when a NEW user message arrives.
            ContextInjector(now_block, name="clock"),
            # trigger="everyTurn": before every model call, including after tool results.
            # A function trigger decides per call, e.g. only when a flag is on.
            ContextInjector(
                profile_block,
                name="profile",
                trigger=lambda context: context.state.get("profile") is not None,
            ),
        ],
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    print(agent("When does my current billing month end, and what plan am I on?"))
    # The injection is stored as a marked {"injected": ...} block, not as plain text.
    print("stored user message:", agent.messages[0]["content"])


if __name__ == "__main__":
    main()
