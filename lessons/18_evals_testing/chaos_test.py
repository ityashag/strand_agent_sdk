"""Lesson 18 - chaos testing: does the agent behave when tools fail?

Run:  uv run python lessons/18_evals_testing/chaos_test.py

Production tools time out, return errors, or come back half empty. ChaosPlugin injects
those failures into tool calls; each base case is expanded into one case per failure mode
(plus a clean baseline). The evaluator checks the agent is honest instead of inventing data.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands import Agent
from strands_evals import Case
from strands_evals.chaos import ChaosCase, ChaosExperiment, ChaosPlugin
from strands_evals.chaos.effects import NetworkError, Timeout, TruncateFields
from strands_evals.evaluators import Evaluator
from strands_evals.types import EvaluationData, EvaluationOutput

sys.path.insert(0, str(Path(__file__).parent))
from agent_under_test import create_support_agent  # noqa: E402

from course_common import setup_logging  # noqa: E402
from course_common.shop import reset_shop  # noqa: E402

EFFECTS = {
    "api_timeout": {"tool_effects": {"get_order_history": [Timeout()]}},
    "api_down": {"tool_effects": {"get_order_history": [NetworkError()]}},
    "partial_response": {"tool_effects": {"get_order_history": [TruncateFields(max_length=40)]}},
}

BASE_CASES = [Case(name="order_status", input="I'm C-1001. What orders do I have?")]


class NoInventedOrders(Evaluator[str, str]):
    """Fail if the answer names an order ID that the shop data does not contain."""

    REAL_ORDERS = {"ORD-5521", "ORD-5530", "ORD-6001"}

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        import re

        mentioned = set(re.findall(r"ORD-\d{4}", str(evaluation_case.actual_output or "")))
        invented = mentioned - self.REAL_ORDERS
        return [
            EvaluationOutput(
                score=float(not invented),
                test_pass=not invented,
                reason=f"invented={sorted(invented)}",
            )
        ]

    async def evaluate_async(
        self, evaluation_case: EvaluationData[str, str]
    ) -> list[EvaluationOutput]:
        return self.evaluate(evaluation_case)


def make_task(agent_factory: Callable[[ChaosCase], Agent]) -> Callable[[ChaosCase], dict[str, Any]]:
    def task(case: ChaosCase) -> dict[str, Any]:
        reset_shop()
        agent = agent_factory(case)  # must include ChaosPlugin(); a fresh agent per case
        return {"output": str(agent(case.input, limits={"turns": 6}))}

    return task


def run_chaos(agent_factory: Callable[[ChaosCase], Agent]) -> Any:
    cases = ChaosCase.expand(BASE_CASES, EFFECTS, include_no_effect_baseline=True)
    experiment = ChaosExperiment(cases=cases, evaluators=[NoInventedOrders()])
    return experiment.run_evaluations(task=make_task(agent_factory))


def main() -> None:
    setup_logging()
    report = run_chaos(lambda case: create_support_agent(plugins=[ChaosPlugin()]))
    for item in report if isinstance(report, list) else [report]:
        item.display(include_actual_output=True)


if __name__ == "__main__":
    main()
