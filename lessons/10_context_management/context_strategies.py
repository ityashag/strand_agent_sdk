"""Lesson 10 - context management: keep the model's window useful, small and cheap.

Run:  uv run python lessons/10_context_management/context_strategies.py

The demo tool returns a 40 KB log. Without context management that log stays in the
history and is re-sent (and paid for) on every later model call. With offloading, the
history keeps a short preview and the full text goes to a "stash" the agent can read back
with a retrieval tool when it really needs it.
"""

from __future__ import annotations

from typing import Any

from strands import Agent, tool
from strands.agent.conversation_manager import (
    SlidingWindowConversationManager,
    SummarizingConversationManager,
)
from strands.experimental.context_manager import ContextManager, Offload
from strands.models.model import Model

from course_common import build_model, setup_logging


@tool
def read_service_logs(service: str) -> str:
    """Read the last 2,000 log lines of a service.

    Args:
        service: Service name, e.g. "payments".
    """
    lines = [
        f"2026-11-21T10:{i // 60:02d}:{i % 60:02d}Z INFO {service} request ok id={i}"
        for i in range(2000)
    ]
    lines[1234] = f"2026-11-21T10:20:34Z ERROR {service} db pool exhausted (max=20)"
    return "\n".join(lines)


TOOLS: list[Any] = [read_service_logs]


def auto_agent(model: Model | None = None) -> Agent:
    """The recommended default: offload big tool results + summarize old turns at ~85%."""
    return Agent(
        model=model or build_model(), tools=TOOLS, context_manager="auto", callback_handler=None
    )


def agentic_agent(model: Model | None = None) -> Agent:
    """The model manages its own context with tools (summarize / truncate / pin)."""
    return Agent(
        model=model or build_model(), tools=TOOLS, context_manager="agentic", callback_handler=None
    )


def custom_agent(model: Model | None = None, summarizer: Model | None = None) -> Agent:
    """Your own pipeline of strategies, evaluated in order."""
    return Agent(
        model=model or build_model(),
        tools=TOOLS,
        context_manager=ContextManager(
            strategies=[
                # Any single tool result over 2,500 tokens -> keep a head/tail preview.
                Offload.truncate("tool_results", {"preview_tokens": 400}).when(threshold=2500),
                # Error results are rarely useful later: drop them once they are old.
                Offload.drop("tool_result_errors").when(preserve_recent=3),
                # When the window is 85% full, summarize everything except the last 8 messages,
                # using a CHEAP model with a domain-specific prompt.
                Offload.summarize(
                    "*",
                    {
                        "model": summarizer or build_model(small=True),
                        "system_prompt": "Summarize this incident investigation. Keep service names, "
                        "error messages, timestamps and decisions.",
                    },
                ).when(utilization=0.85, preserve_recent=8),
                # Named presets also work: "large_tool_offloading", "proactive_summarization",
                # "overflow_protection", "stale_tool_cleanup".
                "overflow_protection",
            ],
            # The stash keeps offloaded originals + gives the agent a retrieve tool.
            # stash=False -> originals are discarded (pure compression, no retrieval).
        ),
        callback_handler=None,
    )


def classic_agent(model: Model | None = None) -> Agent:
    """The older conversation managers. Still supported; context_manager supersedes them."""
    return Agent(
        model=model or build_model(),
        tools=TOOLS,
        conversation_manager=SlidingWindowConversationManager(
            window_size=40,  # keep the last 40 messages
            should_truncate_results=True,  # shorten huge tool results on overflow
        ),
        callback_handler=None,
    )


def summarizing_classic_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        conversation_manager=SummarizingConversationManager(
            summary_ratio=0.3,  # summarize the oldest 30% when the window overflows
            preserve_recent_messages=10,
        ),
        callback_handler=None,
    )


def history_chars(agent: Agent) -> int:
    return sum(len(str(block)) for message in agent.messages for block in message["content"])


def main() -> None:
    setup_logging()
    prompt = "Read the payments logs and tell me the first ERROR line."
    for name, factory in [
        ("no management", classic_agent),
        ("auto", auto_agent),
        ("custom", custom_agent),
    ]:
        agent = factory()
        result = agent(prompt)
        print(f"{name:<14} history={history_chars(agent):>7,} chars | tools={agent.tool_names}")
        print("   ", str(result).strip()[:120])


if __name__ == "__main__":
    main()
