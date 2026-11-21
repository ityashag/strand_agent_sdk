"""Lesson 11 - session managers: the conversation survives a restart.

Run twice and see the agent remember:
    uv run python lessons/11_state_sessions_memory/sessions.py "My name is Asha and I like dark mode."
    uv run python lessons/11_state_sessions_memory/sessions.py "What is my name?"

Without a session manager, everything (messages + agent.state) is lost when the process
stops. A session manager is a hook provider that loads the session when the agent starts
and saves it after each invocation (or each message).
"""

from __future__ import annotations

import sys
from typing import Literal

from strands import Agent
from strands.models.model import Model
from strands.session import SnapshotSessionManager
from strands.session.file_session_manager import FileSessionManager
from strands.session.session_manager import SessionManager
from strands.storage import LocalFileStorage

from course_common import build_model, setup_logging

SESSIONS_DIR = "./sessions"


def snapshot_sessions(session_id: str, base_dir: str = SESSIONS_DIR) -> SessionManager:
    """Recommended: saves the whole agent state together as one snapshot."""
    return SnapshotSessionManager(
        session_id=session_id,
        storage=LocalFileStorage(base_dir),
        # "invocation" (default): save after each agent(...) call.
        # "message": save after every message (survives a crash mid-run, more writes).
        save_latest_on="invocation",
    )
    # Production: storage=S3Storage(bucket="my-agent-sessions", prefix="prod/")
    # or DynamoDB storage (strands-dynamodb-storage), or AgentCore Memory (lesson 19).


def record_sessions(session_id: str, base_dir: str = SESSIONS_DIR) -> SessionManager:
    """The record-based format: one file per message. Still supported for existing data."""
    return FileSessionManager(session_id=session_id, storage_dir=base_dir)
    # S3 version: S3SessionManager(session_id=..., bucket=..., prefix=..., region_name=...)


def build_agent(
    session_id: str,
    model: Model | None = None,
    *,
    kind: Literal["snapshot", "record"] = "snapshot",
    base_dir: str = SESSIONS_DIR,
) -> Agent:
    manager = (
        snapshot_sessions(session_id, base_dir)
        if kind == "snapshot"
        else record_sessions(session_id, base_dir)
    )
    return Agent(
        model=model or build_model(),
        # agent_id names this agent inside the session (a session can hold several agents).
        agent_id="assistant",
        system_prompt="You are a helpful assistant. Remember what the user tells you.",
        session_manager=manager,
        # Long sessions need context management too (lesson 10). It works with the
        # snapshot manager only; the record-based FileSessionManager raises ValueError.
        context_manager="auto" if kind == "snapshot" else None,
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    prompt = sys.argv[1] if len(sys.argv) > 1 else "What do you remember about me?"
    # One session per user conversation. NEVER reuse a session ID across users.
    agent = build_agent(session_id="user-asha-chat-001")
    print("messages loaded from disk:", len(agent.messages))
    print(agent(prompt))


if __name__ == "__main__":
    main()
