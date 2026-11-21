"""Lesson 08 - skills: instructions the agent loads only when it needs them.

Run:  uv run python lessons/08_plugins_skills/skills_agent.py

At start-up the agent sees only each skill's NAME and DESCRIPTION (a few tokens).
When a request matches, the model calls the `skills` tool to load that SKILL.md.
Twenty workflows cost almost nothing until one is actually used: "progressive disclosure".
"""

from __future__ import annotations

from pathlib import Path

from strands import Agent, AgentSkills
from strands.models.model import Model

from course_common import build_model, setup_logging, show_result
from course_common.shop import SHOP_TOOLS

SKILLS_DIR = Path(__file__).with_name("skills")

SYSTEM_PROMPT = """You are a customer service agent for an electronics shop.
When a customer needs help, activate the matching skill and follow its steps exactly."""


def build_skills_plugin() -> AgentSkills:
    return AgentSkills(
        # A folder of skill folders, a single skill folder, Skill objects, or https:// URLs.
        skills=[str(SKILLS_DIR)],
        # strict=True: a broken SKILL.md raises at start-up instead of being skipped.
        strict=True,
        # How many files under scripts/ references/ assets/ to list for a skill.
        max_resource_files=20,
    )


def build_agent(model: Model | None = None) -> Agent:
    return Agent(
        model=model or build_model(),
        tools=SHOP_TOOLS,
        plugins=[build_skills_plugin()],
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


def main() -> None:
    setup_logging()
    agent = build_agent()
    print("tools:", agent.tool_names)  # note the extra "skills" tool added by the plugin
    result = agent("Hi, I'm C-1001. I want a refund for my headphones, they broke.")
    print(result)
    show_result(result, agent.messages)


if __name__ == "__main__":
    main()
