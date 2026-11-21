"""The agent loop written by hand, with NO SDK, so you can see there is no magic.

Run:  uv run python lessons/01_agent_loop/loop_by_hand.py

Strands does exactly these four steps for you, plus a lot of production work around them
(streaming, retries, limits, hooks, tracing, context management).
"""

from __future__ import annotations

from typing import Any

# The "tools" the model may use. In Strands these are @tool functions.
TOOLS: dict[str, Any] = {
    "get_weather": lambda city: {"city": city, "temp_c": 31, "sky": "sunny"},
}


def fake_llm(messages: list[dict[str, Any]], tool_names: list[str]) -> dict[str, Any]:
    """Pretend model. A real model reads the whole message list and decides the next step."""
    last = messages[-1]
    if "tool_result" not in last:
        # Step 2: the model decides it needs live data, so it asks for a tool.
        return {"tool_call": {"name": "get_weather", "input": {"city": "Delhi"}}}
    data = last["tool_result"]
    return {"text": f"It is {data['temp_c']} C and {data['sky']} in {data['city']}."}


def run_agent(prompt: str, max_turns: int = 5) -> tuple[str, list[dict[str, Any]]]:
    """The agent loop: model -> tool -> model -> ... -> answer."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

    for turn in range(1, max_turns + 1):
        # Step 1: send the WHOLE context (prompt + history + tool list) to the model.
        reply = fake_llm(messages, list(TOOLS))

        # Step 4: no tool requested -> the task is finished.
        if "text" in reply:
            messages.append({"role": "assistant", "content": reply["text"]})
            print(f"turn {turn}: model answered")
            return reply["text"], messages

        # Step 2 -> 3: the model asked for a tool; the HARNESS (not the model) runs it.
        call = reply["tool_call"]
        print(f"turn {turn}: model asked for tool {call['name']}({call['input']})")
        messages.append({"role": "assistant", "tool_call": call})
        output = TOOLS[call["name"]](**call["input"])
        # The result goes back into the context and the loop repeats.
        messages.append({"role": "user", "tool_result": output})

    # A production harness always has a limit, otherwise a confused model loops forever.
    raise RuntimeError(f"turn limit of {max_turns} reached")


if __name__ == "__main__":
    answer, history = run_agent("What's the weather in Delhi?")
    print("\nanswer:", answer)
    print("history has", len(history), "messages:")
    for message in history:
        print("  ", message)
