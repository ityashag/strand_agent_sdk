"""Lesson 14 - swarms: agents hand work to each other; nobody fixes the order in advance.

Run:  uv run python lessons/14_swarms/debugging_swarm.py

Good when you can't draw the workflow ahead of time, e.g. an incident: the next step depends
on what the last step found. Strands gives every agent a `handoff_to_agent` tool. A handoff
is a full transfer of control (not a function call), and the next agent sees what the
previous ones found (shared context).
"""

from __future__ import annotations

from collections.abc import Callable

from strands import Agent, tool
from strands.models.model import Model
from strands.multiagent import Swarm

from course_common import build_model, setup_logging

ModelFactory = Callable[[str], Model]


# --- mock observability tools ---------------------------------------------------------
@tool
def check_application_logs(service: str) -> str:
    """Read recent error logs of a service.

    Args:
        service: Service name, e.g. "payments".
    """
    return f"{service}: 1,204 x 'DB connection timeout' since 10:02 UTC; 0 errors before 10:02."


@tool
def check_metrics_dashboard(service: str) -> str:
    """Read CPU, memory, latency and error-rate metrics of a service.

    Args:
        service: Service name.
    """
    return f"{service}: p99 latency 4.8s (normal 300ms), error rate 25%, DB pool usage 100% since 10:02."


@tool
def check_recent_deployments(service: str) -> str:
    """List deployments of a service in the last 24 hours.

    Args:
        service: Service name.
    """
    return f"{service}: v2.14.0 deployed 10:00 UTC - changed DB pool size from 50 to 5."


def _models(name: str) -> Model:
    return build_model()


def build_swarm(models: ModelFactory = _models) -> Swarm:
    def agent(name: str, prompt: str, tools: list) -> Agent:
        return Agent(
            name=name, system_prompt=prompt, tools=tools, model=models(name), callback_handler=None
        )

    triage = agent(
        "triage",
        "You do the first assessment of an incident. Hand off to the specialist that fits best. "
        "Do not investigate yourself.",
        [],
    )
    log_analyst = agent(
        "log_analyst",
        "You analyse application logs. If errors point to infrastructure or a release, hand off to "
        "deployment_reviewer. Otherwise give the root cause.",
        [check_application_logs],
    )
    metrics_analyst = agent(
        "metrics_analyst",
        "You analyse metrics. Hand off based on what you find.",
        [check_metrics_dashboard],
    )
    deployment_reviewer = agent(
        "deployment_reviewer",
        "You review recent deployments and give the final root cause and the fix. Do not hand off.",
        [check_recent_deployments],
    )
    return Swarm(
        [triage, log_analyst, metrics_analyst, deployment_reviewer],
        entry_point=triage,
        # --- safety limits: nothing structural stops a swarm from bouncing around ------
        max_handoffs=10,  # total handoffs
        max_iterations=10,  # total agent turns
        execution_timeout=300.0,  # seconds for the whole swarm
        node_timeout=120.0,  # seconds for one agent turn
        # Stop ping-pong: in the last 6 handoffs there must be at least 2 different agents.
        repetitive_handoff_detection_window=6,
        repetitive_handoff_min_unique_agents=2,
        id="incident-swarm",
    )


def main() -> None:
    setup_logging()
    swarm = build_swarm()
    result = swarm("Payment service returning 500 errors for 25% of requests. Started 30 min ago.")
    print("status :", result.status)
    print("path   :", " -> ".join(node.node_id for node in result.node_history))
    last = result.node_history[-1].node_id if result.node_history else None
    if last:
        print(result.results[last].result)


if __name__ == "__main__":
    main()
