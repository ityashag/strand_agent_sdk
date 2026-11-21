"""Lesson 01 - the "batteries included" agent: SDK-vended tools + automatic context management.

Run:  uv run python lessons/01_agent_loop/agent_with_defaults.py
Needs a real model (not MODEL_PROVIDER=fake) and internet access for web_fetch.

WARNING: vended tools act with YOUR permissions. file_editor can write files where you run
it. The official sample also adds `shell`, which can run any command on your machine; we
leave it out on purpose. Lesson 16 shows how to limit tools; Strands Shell/Box sandbox them.
"""

from __future__ import annotations

from strands import Agent
from strands.models.model import Model
from strands.vended_tools import file_editor
from strands.vended_tools.web_fetch import web_fetch

from course_common import build_model, setup_logging, show_result


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=[web_fetch, file_editor],
        system_prompt="You are a research assistant. Cite the URLs you used.",
        # "auto": offload big tool results, summarize old messages, and compress
        # proactively at ~85% of the context window. Lesson 10 explains every option.
        context_manager="auto",
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    result = agent(
        "Read https://strandsagents.com/docs/learning/how-agents-really-work/ and write a "
        "5-bullet summary to report.md"
    )
    show_result(result)


if __name__ == "__main__":
    main()
