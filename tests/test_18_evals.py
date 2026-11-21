"""Lesson 18: the eval suite and chaos experiment, run offline with scripted models."""

from __future__ import annotations

from strands_evals.chaos import ChaosPlugin

from course_common import ScriptedModel, ToolCall

LOOKUP = ToolCall("lookup_customer", {"customer_id": "C-1001"})
HISTORY = ToolCall("get_order_history", {"customer_id": "C-1001"})
REFUND = ToolCall("process_refund", {"order_id": "ORD-5521", "amount": 79.99, "reason": "broke"})

GOOD = {
    "refund-full-workflow": [LOOKUP, HISTORY, REFUND, "Refund RF-0001 done; 3-5 business days."],
    "missing-customer-id": ["Could you share your customer ID?"],
    "order-status": [HISTORY, "Your USB-C hub has shipped."],
}


def _suite(lesson, scripts):
    evals = lesson("18_evals_testing/run_evals.py")
    agent_module = lesson("18_evals_testing/agent_under_test.py")
    return evals.run_suite(
        lambda case: agent_module.create_support_agent(ScriptedModel(scripts[case.name])),
        with_judges=False,
    )


def test_good_behaviour_passes_every_deterministic_check(lesson):
    report = _suite(lesson, GOOD)
    assert report.overall_score == 1.0
    assert all(report.test_passes)


def test_skipping_a_step_and_promising_fail_the_suite(lesson):
    bad = {**GOOD, "refund-full-workflow": [LOOKUP, REFUND, "Done, I guarantee it by tomorrow."]}
    report = _suite(lesson, bad)
    assert report.overall_score < 1.0
    assert report.test_passes.count(False) == 2  # wrong tool order + forbidden word


def test_chaos_cases_inject_tool_failures(lesson):
    chaos = lesson("18_evals_testing/chaos_test.py")
    agent_module = lesson("18_evals_testing/agent_under_test.py")
    models: dict[str, ScriptedModel] = {}

    def factory(case):
        model = ScriptedModel([HISTORY, "Sorry, the order system is unavailable right now."])
        models[case.name] = model
        return agent_module.create_support_agent(model, plugins=[ChaosPlugin()])

    report = chaos.run_chaos(factory)

    assert all(report.test_passes)
    timeout_result = str(models["order_status|api_timeout"].calls[1].messages)
    assert "timed out" in timeout_result
    assert "ORD-5521" in str(models["order_status|baseline"].calls[1].messages)
