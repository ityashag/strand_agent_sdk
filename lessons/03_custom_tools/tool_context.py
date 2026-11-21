"""Lesson 03 - ToolContext: what a tool can see besides its arguments.

Run:  uv run python lessons/03_custom_tools/tool_context.py

The model fills the arguments. Your APPLICATION fills invocation_state. That split is a
security boundary: the user ID comes from your login system, never from the model, so a
prompt like "act as user 42" cannot change whose data the tool reads.
"""

from __future__ import annotations

from strands import Agent, ToolContext, tool
from strands.models.model import Model

from course_common import build_model, setup_logging

NOTES: dict[str, list[str]] = {"user-7": ["Prefers email over phone"], "user-42": ["VIP"]}


@tool(context=True)
def read_my_notes(tool_context: ToolContext) -> str:
    """Read the saved notes about the current user."""
    # Set by the app: agent(prompt, invocation_state={"user_id": ...}). The model can't change it.
    user_id = tool_context.invocation_state["user_id"]

    # agent.state: key/value store on the agent, NOT sent to the model, saved by sessions.
    calls = tool_context.agent.state.get("notes_reads") or 0
    tool_context.agent.state.set("notes_reads", calls + 1)

    # tool_use: the raw request from the model (its ID and input).
    tool_use_id = tool_context.tool_use["toolUseId"]
    notes = NOTES.get(user_id, [])
    return f"[{tool_use_id}] notes for {user_id}: {notes or 'none'}"


@tool(context=True)
def export_report(rows: int, tool_context: ToolContext) -> str:
    """Build a long report row by row. Stops early if the agent is cancelled.

    Args:
        rows: Number of rows to build (1-1000).
    """
    built = 0
    for _ in range(rows):
        # Cancellation is cooperative: long tools must check the signal (lesson 15).
        if tool_context.cancel_signal.is_set():
            return f"cancelled after {built} rows"
        built += 1
    return f"report ready with {built} rows"


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=[read_my_notes, export_report],
        system_prompt="You help the signed-in user. Use read_my_notes when asked about them.",
        state={"notes_reads": 0},
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    # invocation_state lives for ONE call and is never shown to the model.
    result = agent("What do you know about me?", invocation_state={"user_id": "user-7"})
    print(result)
    print("notes_reads in agent.state:", agent.state.get("notes_reads"))


if __name__ == "__main__":
    main()
