"""A scripted model for running and testing agents without calling a real LLM.

Why this exists
---------------
A real model costs money, needs credentials, and gives a slightly different answer every
time. That makes unit tests slow and flaky. In production teams you test the *harness*
(tools, hooks, limits, state, routing) with a fake model that answers from a script, and
you test the *model's judgement* separately with evals (lesson 18).

How it works
------------
Strands talks to every provider through one interface: ``Model.stream()`` yields
Bedrock-style stream events (messageStart, contentBlockDelta, messageStop, metadata).
``ScriptedModel`` yields the same events, so the Agent cannot tell it is fake.

Each item in ``turns`` is the model's reply for one model call:

* ``"some text"``                 -> the model answers with text and stops (end_turn)
* ``ToolCall("name", {...})``     -> the model asks to run one tool
* ``[ToolCall(...), ToolCall()]`` -> the model asks to run several tools in one turn
* ``["thinking...", ToolCall()]`` -> text plus a tool call in one turn

When the script runs out the model replies with ``default_text`` (or echoes the user).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel
from strands.models.model import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent
from strands.types.tools import ToolSpec

T = TypeVar("T", bound=BaseModel)


@dataclass
class ToolCall:
    """One tool call the scripted model should make."""

    name: str
    input: dict[str, Any] = field(default_factory=dict)


Block = str | ToolCall
Turn = Block | Sequence[Block]


@dataclass
class ModelCall:
    """What the agent sent to the model on one call (useful for assertions in tests)."""

    messages: Messages
    tool_names: list[str]
    system_prompt: str | None


class ScriptedModel(Model):
    """A deterministic, offline model that replays a script of turns."""

    def __init__(
        self,
        turns: Sequence[Turn] | None = None,
        *,
        default_text: str | None = None,
        model_id: str = "scripted-model",
        context_window_limit: int | None = 200_000,
    ) -> None:
        self._turns: list[Turn] = list(turns or [])
        self._default_text = default_text
        self._config: dict[str, Any] = {"model_id": model_id}
        if context_window_limit:
            # Lets context management (lesson 10) compute "% of the window used".
            self._config["context_window_limit"] = context_window_limit
        self.calls: list[ModelCall] = []
        self._tool_counter = 0

    # --- Model interface -------------------------------------------------------------
    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    async def structured_output(
        self,
        output_model: type[T],
        prompt: Messages,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, T | Any]]:
        # The agent normally gets structured output through a forced tool call (see
        # lesson 05), so this direct path is only used when you call it yourself.
        turn = self._next_turn(prompt)
        call = turn if isinstance(turn, ToolCall) else None
        if call is None:
            raise ValueError("ScriptedModel.structured_output needs a ToolCall turn")
        yield {"output": output_model(**call.input)}

    async def stream(
        self,
        messages: Messages,
        tool_specs: list[ToolSpec] | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterable[StreamEvent]:
        self.calls.append(
            ModelCall(
                messages=[dict(m) for m in messages],  # type: ignore[misc]
                tool_names=[spec["name"] for spec in tool_specs or []],
                system_prompt=system_prompt,
            )
        )
        turn = self._next_turn(messages)
        blocks: list[Block] = [turn] if isinstance(turn, (str, ToolCall)) else list(turn)

        yield {"messageStart": {"role": "assistant"}}
        used_tool = False
        output_chars = 0
        for block in blocks:
            if isinstance(block, str):
                yield {"contentBlockStart": {"start": {}}}
                # Stream text in small chunks, like a real model, so callbacks see deltas.
                for i in range(0, len(block), 24):
                    yield {"contentBlockDelta": {"delta": {"text": block[i : i + 24]}}}
                yield {"contentBlockStop": {}}
                output_chars += len(block)
            else:
                used_tool = True
                self._tool_counter += 1
                tool_use_id = f"tooluse_{self._tool_counter:04d}"
                yield {
                    "contentBlockStart": {
                        "start": {"toolUse": {"toolUseId": tool_use_id, "name": block.name}}
                    }
                }
                yield {
                    "contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(block.input)}}}
                }
                yield {"contentBlockStop": {}}
                output_chars += len(json.dumps(block.input))
        yield {"messageStop": {"stopReason": "tool_use" if used_tool else "end_turn"}}

        input_tokens = sum(len(json.dumps(m.get("content", []))) for m in messages) // 4
        output_tokens = max(1, output_chars // 4)
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": input_tokens,
                    "outputTokens": output_tokens,
                    "totalTokens": input_tokens + output_tokens,
                },
                "metrics": {"latencyMs": 1},
            }
        }

    # --- helpers ---------------------------------------------------------------------
    @property
    def remaining_turns(self) -> int:
        return len(self._turns)

    def _next_turn(self, messages: Messages) -> Turn:
        if self._turns:
            return self._turns.pop(0)
        if self._default_text is not None:
            return self._default_text
        return f"(fake model) You said: {_last_user_text(messages)}"


def _last_user_text(messages: Messages) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        for block in message.get("content", []):
            if "text" in block:
                return str(block["text"])[:200]
    return ""
