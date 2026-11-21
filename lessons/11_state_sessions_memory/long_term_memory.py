"""Lesson 11 - long-term memory: facts that carry across DIFFERENT conversations.

Run:  uv run python lessons/11_state_sessions_memory/long_term_memory.py

Session = "continue THIS conversation".
Memory  = "remember facts about this user in ANY future conversation", without replaying
          old chats. The agent gets a search_memory tool (and, if allowed, add_memory),
          and relevant memories can be injected into the prompt automatically.
"""

from __future__ import annotations

from strands import Agent
from strands.memory import MemoryManager
from strands.models.model import Model
from strands.storage import LocalFileStorage
from strands.vended_memory_stores.file_memory_store import FileMemoryStore

from course_common import build_model, setup_logging

MEMORY_DIR = "./memory_store"


def build_memory(user_id: str, base_dir: str = MEMORY_DIR) -> MemoryManager:
    # One store per user: a user's memories can never show up in another user's chat.
    store = FileMemoryStore(
        name="preferences",
        description="Facts and preferences this customer told us.",
        writable=True,
        max_search_results=5,
        storage=LocalFileStorage(f"{base_dir}/{user_id}"),
    )
    return MemoryManager(
        stores=[store],
        search_tool_config=True,  # search_memory tool
        add_tool_config=True,  # add_memory tool (the model decides what to save)
        injection=True,  # relevant memories are folded into the prompt automatically
    )


def build_agent(user_id: str, model: Model | None = None, base_dir: str = MEMORY_DIR) -> Agent:
    return Agent(
        model=model or build_model(),
        memory_manager=build_memory(user_id, base_dir),
        system_prompt="You are a support agent. Save lasting customer preferences with add_memory.",
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    # Conversation 1
    first = build_agent("asha")
    print(first("Please always contact me by email, never by phone."))
    # Conversation 2 - a brand new agent, no shared history, same user
    second = build_agent("asha")
    print(second("How do you usually contact me?"))


if __name__ == "__main__":
    main()
