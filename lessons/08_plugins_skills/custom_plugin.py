"""Lesson 08 - write your own plugin: hooks + tools + state packaged as one reusable unit.

Run:  uv run python lessons/08_plugins_skills/custom_plugin.py

A hook is one behaviour. A plugin bundles several (hooks, tools, setup) that belong together,
so a platform team can ship "TokenBudget" or "CompanyAudit" and every agent adds one line.
"""

from __future__ import annotations

from strands import Agent, Plugin, ToolContext, tool
from strands.hooks import AfterInvocationEvent, BeforeInvocationEvent
from strands.models.model import Model
from strands.plugins import hook

from course_common import build_model, setup_logging


class TokenBudget(Plugin):
    """Refuse new requests once a conversation has used its token budget."""

    name = "token-budget"  # stable ID, required

    def __init__(self, max_tokens: int) -> None:
        super().__init__()  # discovers the @hook and @tool methods below
        self.max_tokens = max_tokens

    def init_agent(self, agent: Agent) -> None:
        # Runs once when the plugin is attached: set up state, add more hooks, etc.
        if agent.state.get("tokens_used") is None:
            agent.state.set("tokens_used", 0)

    @hook
    def refuse_when_spent(self, event: BeforeInvocationEvent) -> None:
        used = event.agent.state.get("tokens_used") or 0
        if used >= self.max_tokens:
            event.cancel = (
                f"Token budget of {self.max_tokens} used up ({used}). Start a new conversation."
            )

    @hook
    def record_usage(self, event: AfterInvocationEvent) -> None:
        latest = event.result.metrics.latest_agent_invocation if event.result else None
        if latest is not None:
            used = (event.agent.state.get("tokens_used") or 0) + latest.usage.get("totalTokens", 0)
            event.agent.state.set("tokens_used", used)

    @tool(context=True)
    def remaining_token_budget(self, tool_context: ToolContext) -> str:
        """Tell how many tokens are left in this conversation's budget."""
        used = tool_context.agent.state.get("tokens_used") or 0
        return f"{max(0, self.max_tokens - used)} of {self.max_tokens} tokens left"


def build_agent(model: Model | None = None, max_tokens: int = 2_000) -> Agent:
    return Agent(
        model=model or build_model(),
        plugins=[TokenBudget(max_tokens=max_tokens)],  # tools and hooks come with it
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent(max_tokens=100)
    for question in ["Explain DNS in one line.", "Now explain TCP.", "And UDP?", "And QUIC?"]:
        result = agent(question)
        print(
            f"[{result.stop_reason}] {str(result).strip()[:80]} | used={agent.state.get('tokens_used')}"
        )


if __name__ == "__main__":
    main()
