"""Lesson 18 - an evaluation suite with Strands Evals.

Run:  uv run python lessons/18_evals_testing/run_evals.py
      (with MODEL_PROVIDER=fake only the deterministic checks are meaningful)

Agents are non-deterministic: the same input can give different (equally valid) wording or
tool order. So instead of `assert output == expected` an eval suite combines:
  - deterministic checks  (tool called? order right? forbidden words? JSON valid?)  free, exact
  - LLM judges            (is the answer correct, helpful, polite?)                costs tokens
and reports a pass rate you compare between versions. A change ships only if it does not regress.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from strands import Agent
from strands_evals import Case, Experiment
from strands_evals.evaluators import Evaluator, OutputEvaluator, TrajectoryEvaluator
from strands_evals.extractors import tools_use_extractor
from strands_evals.types import EvaluationData, EvaluationOutput, TaskOutput

sys.path.insert(0, str(Path(__file__).parent))
from agent_under_test import create_support_agent  # noqa: E402

from course_common import build_model, get_settings, setup_logging  # noqa: E402
from course_common.shop import reset_shop  # noqa: E402

# --- 1. Cases: input + what "good" looks like ----------------------------------------
CASES: list[Case] = [
    Case(
        name="refund-full-workflow",
        input="I'm C-1001. Refund order ORD-5521, the headphones broke. Yes, I confirm the refund.",
        expected_output="Refund processed; money arrives in 3-5 business days.",
        expected_trajectory=["lookup_customer", "get_order_history", "process_refund"],
        metadata={"forbidden": ["guarantee"]},
    ),
    Case(
        name="missing-customer-id",
        input="I want a refund.",
        expected_output="Asks for the customer ID before doing anything.",
        expected_trajectory=[],
    ),
    Case(
        name="order-status",
        input="I'm C-1001. Where is my USB-C hub?",
        expected_output="The USB-C hub (ORD-5530) has shipped and is on the way.",
        expected_trajectory=["get_order_history"],
    ),
]


# --- 2. Evaluators ---------------------------------------------------------------------
class ExpectedToolsInOrder(Evaluator[str, str]):
    """Deterministic: the expected tools appear in this order (extra tools allowed).
    An empty expectation means "no tools at all"."""

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        expected = list(evaluation_case.expected_trajectory or [])
        actual = [step["name"] for step in (evaluation_case.actual_trajectory or [])]
        if not expected:
            ok = not actual
            return [
                EvaluationOutput(
                    score=float(ok), test_pass=ok, reason=f"expected no tools, got {actual}"
                )
            ]
        position = 0
        for name in actual:
            if position < len(expected) and name == expected[position]:
                position += 1
        ok = position == len(expected)
        return [
            EvaluationOutput(
                score=position / len(expected), test_pass=ok, reason=f"actual={actual}"
            )
        ]

    async def evaluate_async(
        self, evaluation_case: EvaluationData[str, str]
    ) -> list[EvaluationOutput]:
        return self.evaluate(evaluation_case)


class NoForbiddenWords(Evaluator[str, str]):
    """Deterministic: policy words never appear in the answer."""

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        forbidden = (evaluation_case.metadata or {}).get("forbidden", [])
        text = str(evaluation_case.actual_output or "").lower()
        hits = [word for word in forbidden if word in text]
        return [EvaluationOutput(score=float(not hits), test_pass=not hits, reason=f"hits={hits}")]

    async def evaluate_async(
        self, evaluation_case: EvaluationData[str, str]
    ) -> list[EvaluationOutput]:
        return self.evaluate(evaluation_case)


def llm_judges() -> list[Evaluator[Any, Any]]:
    """LLM-as-judge evaluators. Use a DIFFERENT (and cheaper) model than the agent's."""
    judge = build_model(small=True, temperature=0)
    return [
        OutputEvaluator(
            rubric="Pass if the response is accurate, polite, and does what the expected output describes. "
            "Score 0-1.",
            model=judge,
        ),
        TrajectoryEvaluator(
            rubric="Pass if the tools were used in a sensible order for the request. Score 0-1.",
            model=judge,
        ),
    ]


# --- 3. Task: run the agent for one case and return what the evaluators need ----------
def make_task(agent_factory: Callable[[Case], Agent]) -> Callable[[Case], TaskOutput]:
    def task(case: Case) -> TaskOutput:
        reset_shop()  # every case starts from the same data
        agent = agent_factory(case)  # a FRESH agent per case: no leaking between cases
        response = agent(case.input, limits={"turns": 8})
        trajectory = tools_use_extractor.extract_agent_tools_used_from_messages(agent.messages)
        return TaskOutput(output=str(response), trajectory=trajectory)

    return task


def run_suite(agent_factory: Callable[[Case], Agent], *, with_judges: bool) -> Any:
    evaluators: list[Evaluator[Any, Any]] = [ExpectedToolsInOrder(), NoForbiddenWords()]
    if with_judges:
        evaluators += llm_judges()
    experiment = Experiment(cases=CASES, evaluators=evaluators)
    return experiment.run_evaluations(task=make_task(agent_factory))


def main() -> None:
    setup_logging()
    real_model = get_settings().model_provider != "fake"
    reports = run_suite(lambda case: create_support_agent(), with_judges=real_model)
    for report in reports if isinstance(reports, list) else [reports]:
        report.display(include_actual_output=True, include_actual_trajectory=True)


if __name__ == "__main__":
    main()
