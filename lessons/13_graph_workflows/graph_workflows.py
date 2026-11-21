"""Lesson 13 - graph workflows: you fix the order, agents do the work.

Run:  uv run python lessons/13_graph_workflows/graph_workflows.py

Use a graph when you can draw the workflow on a whiteboard. Each node is an agent (or a
whole graph/swarm); each edge "A -> B" means "B waits for A". Nodes with no dependency
on each other run in parallel.

Two graphs:
  1. fan-out / fan-in:  research -> (analysis || summary) -> report
  2. review loop:       draft -> review -> (approved? -> publish : back to draft)
"""

from __future__ import annotations

from collections.abc import Callable

from strands import Agent
from strands.models.model import Model
from strands.multiagent import GraphBuilder
from strands.multiagent.graph import Graph, GraphState

from course_common import build_model, setup_logging

ModelFactory = Callable[[str], Model]


def _default_models(node_id: str) -> Model:
    return build_model()


def _agent(node_id: str, prompt: str, models: ModelFactory) -> Agent:
    return Agent(name=node_id, system_prompt=prompt, model=models(node_id), callback_handler=None)


def build_report_graph(models: ModelFactory = _default_models) -> Graph:
    builder = GraphBuilder()
    builder.add_node(
        _agent("research", "Gather the key facts about the topic. Bullet points.", models),
        "research",
    )
    builder.add_node(
        _agent("analysis", "Find patterns, risks and trends in the research.", models), "analysis"
    )
    builder.add_node(
        _agent("summary", "Condense the research into 5 key points.", models), "summary"
    )
    builder.add_node(
        _agent("report", "Write a final one-page report from the analysis and summary.", models),
        "report",
    )

    builder.add_edge("research", "analysis")
    builder.add_edge("research", "summary")  # analysis and summary run in parallel
    builder.add_edge("analysis", "report")
    builder.add_edge("summary", "report")  # report waits for BOTH

    # Safety limits (always set them).
    builder.set_execution_timeout(600)  # whole graph, seconds
    builder.set_node_timeout(180)  # one node, seconds
    builder.set_graph_id("report-graph")  # shows up in traces and sessions
    return builder.build()


def approved(state: GraphState) -> bool:
    """Edge condition: follow this edge only if the reviewer approved."""
    review = state.results.get("review")
    return review is not None and "APPROVED" in str(review.result).upper()


def rejected(state: GraphState) -> bool:
    return not approved(state)


def build_review_loop(models: ModelFactory = _default_models) -> Graph:
    builder = GraphBuilder()
    builder.add_node(
        _agent("draft", "Write or improve a product announcement (max 80 words).", models), "draft"
    )
    builder.add_node(
        _agent(
            "review",
            "Review the announcement. Reply APPROVED, or REJECTED with what to fix.",
            models,
        ),
        "review",
    )
    builder.add_node(
        _agent("publish", "Format the approved announcement as final markdown.", models), "publish"
    )

    builder.set_entry_point("draft")
    builder.add_edge("draft", "review")
    builder.add_edge("review", "publish", condition=approved)
    builder.add_edge("review", "draft", condition=rejected)  # a cycle

    # A cycle MUST have a cap, or a picky reviewer loops forever.
    builder.set_max_node_executions(7)  # total node runs in this graph
    builder.reset_on_revisit(False)  # False: the drafter keeps its history and sees past feedback
    builder.set_execution_timeout(300)
    return builder.build()


def main() -> None:
    setup_logging()
    graph = build_report_graph()
    # invocation_state is shared with every node but NOT shown to the models (user IDs, flags).
    result = graph(
        "The impact of AI agents on customer support", invocation_state={"user_id": "u-7"}
    )
    print("status:", result.status)
    print("order :", [node.node_id for node in result.execution_order])
    print(result.results["report"].result)


if __name__ == "__main__":
    main()
