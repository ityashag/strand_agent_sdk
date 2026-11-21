"""Lesson 07 - interrupts: pause the agent and ask a human before a risky action.

Run:  uv run python lessons/07_hooks_interrupts/approval_interrupt.py

Flow:
  1. agent(prompt) -> a hook calls event.interrupt(...) -> the run STOPS
     with stop_reason == "interrupt" and result.interrupts = [questions]
  2. your app asks a human (CLI, Slack button, web form...)
  3. agent([{"interruptResponse": {"interruptId": ..., "response": ...}}]) -> the run RESUMES
     exactly where it stopped; event.interrupt(...) now returns the human's answer.

Between step 1 and 3 the agent can be saved with a session manager (lesson 11), so the
human can answer hours later, even on another server.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from strands import Agent, tool
from strands.agent.agent_result import AgentResult
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from strands.models.model import Model
from strands.types.interrupt import InterruptResponseContent

from course_common import build_model, setup_logging

FILES = {"report.txt": "Q3 numbers", "old.log": "debug noise", "notes.md": "ideas"}


@tool
def list_files() -> list[str]:
    """List the files in the workspace."""
    return sorted(FILES)


@tool
def delete_file(path: str) -> str:
    """Delete a file from the workspace. Cannot be undone.

    Args:
        path: File name to delete.
    """
    if path not in FILES:
        return f"{path} does not exist"
    del FILES[path]
    return f"deleted {path}"


class ApprovalHook(HookProvider):
    """Ask a human before any tool in `needs_approval` runs."""

    def __init__(self, app_name: str, needs_approval: set[str]) -> None:
        self.app_name = app_name
        self.needs_approval = needs_approval

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.approve)

    def approve(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]
        if name not in self.needs_approval:
            return
        # Interrupt names must be unique per event; namespace them with your app name.
        answer = event.interrupt(
            f"{self.app_name}-approve-{name}",
            reason={"tool": name, "input": event.tool_use["input"]},  # must be JSON-serializable
        )
        if str(answer).strip().lower() not in {"y", "yes"}:
            event.cancel_tool = f"The user did not approve {name}. Do not retry it."


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=[list_files, delete_file],
        hooks=[ApprovalHook("files", needs_approval={"delete_file"})],
        system_prompt="You manage workspace files. Delete only what the user asks for.",
        callback_handler=None,
    )


def run_with_approvals(agent: Agent, prompt: str, ask_human: Callable[[Any], str]) -> AgentResult:
    """Run the agent; whenever it is interrupted, ask the human and resume."""
    result = agent(prompt)
    while result.stop_reason == "interrupt":
        responses: list[InterruptResponseContent] = [
            {
                "interruptResponse": {
                    "interruptId": interrupt.id,
                    "response": ask_human(interrupt.reason),
                }
            }
            for interrupt in result.interrupts or []
        ]
        result = agent(responses)  # resume
    return result


def main() -> None:
    setup_logging()
    agent = build_agent()

    def ask_cli(reason: Any) -> str:
        return input(f"Approve {reason['tool']} {reason['input']}? (y/N): ")

    result = run_with_approvals(agent, "Delete old.log please.", ask_cli)
    print(result)
    print("files now:", sorted(FILES))


if __name__ == "__main__":
    main()
