"""Lessons 12-14: agents as tools, graphs, swarms - offline."""

from __future__ import annotations

from strands.multiagent.base import Status

from course_common import ScriptedModel, ToolCall


def test_orchestrator_delegates_to_isolated_specialists(lesson):
    module = lesson("12_agents_as_tools/agents_as_tools.py")
    billing_model = ScriptedModel(
        [ToolCall("get_order_history", {"customer_id": "C-1001"}), "Total spent: $124.99."]
    )
    policy_model = ScriptedModel(["Refunds take 3-5 business days."])
    lead_model = ScriptedModel(
        [
            [
                ToolCall("billing_specialist", {"input": "C-1001 total?"}),
                ToolCall("policy_specialist", {"input": "refund time?"}),
            ],
            "You spent $124.99; refunds take 3-5 business days.",
        ]
    )
    billing = module.billing_specialist(billing_model)
    lead = module.build_orchestrator(lead_model, billing, module.policy_specialist(policy_model))

    result = lead("How much did I spend and how long do refunds take?")

    assert "$124.99" in str(result)
    results = [b["toolResult"]["content"][0]["text"] for b in lead.messages[2]["content"]]
    assert "Total spent: $124.99." in results[0]
    # The specialist's own tool call stayed in ITS context, not the orchestrator's.
    assert "get_order_history" not in str(lead.messages)
    # The specialist only saw the orchestrator's short question, not the user's whole chat.
    assert billing.messages[0]["content"][0]["text"] == "C-1001 total?"


def test_report_graph_fans_out_and_joins(lesson):
    module = lesson("13_graph_workflows/graph_workflows.py")
    models = {
        n: ScriptedModel([text])
        for n, text in {
            "research": "facts",
            "analysis": "trend",
            "summary": "points",
            "report": "REPORT",
        }.items()
    }
    result = module.build_report_graph(lambda n: models[n])("topic")

    order = [node.node_id for node in result.execution_order]
    assert result.status == Status.COMPLETED
    assert order[0] == "research" and order[-1] == "report"
    report_input = str(models["report"].calls[0].messages[-1]["content"])
    assert "From analysis" in report_input and "From summary" in report_input


def test_review_loop_revisits_draft_until_approved(lesson):
    module = lesson("13_graph_workflows/graph_workflows.py")
    models = {
        "draft": ScriptedModel(["v1", "v2"]),
        "review": ScriptedModel(["REJECTED: too long", "APPROVED"]),
        "publish": ScriptedModel(["# Final"]),
    }
    result = module.build_review_loop(lambda n: models[n])("announce X")
    assert [n.node_id for n in result.execution_order] == [
        "draft",
        "review",
        "draft",
        "review",
        "publish",
    ]


def test_review_loop_is_capped(lesson):
    module = lesson("13_graph_workflows/graph_workflows.py")
    models = {
        "draft": ScriptedModel(default_text="v"),
        "review": ScriptedModel(default_text="REJECTED"),
        "publish": ScriptedModel(["never"]),
    }
    result = module.build_review_loop(lambda n: models[n])("announce")
    assert result.status == Status.FAILED
    assert len(result.execution_order) == 7


def test_swarm_hands_off_until_root_cause(lesson):
    module = lesson("14_swarms/debugging_swarm.py")

    def handoff(to: str, message: str) -> ToolCall:
        return ToolCall("handoff_to_agent", {"agent_name": to, "message": message})

    models = {
        "triage": ScriptedModel([handoff("log_analyst", "500s on payments")]),
        "log_analyst": ScriptedModel(
            [
                ToolCall("check_application_logs", {"service": "payments"}),
                handoff("deployment_reviewer", "DB timeouts"),
            ]
        ),
        "deployment_reviewer": ScriptedModel(
            [
                ToolCall("check_recent_deployments", {"service": "payments"}),
                "Root cause: pool 50->5. Roll back.",
            ]
        ),
        "metrics_analyst": ScriptedModel(["unused"]),
    }
    result = module.build_swarm(lambda n: models[n])("payments 500s")

    assert result.status == Status.COMPLETED
    assert [n.node_id for n in result.node_history] == [
        "triage",
        "log_analyst",
        "deployment_reviewer",
    ]
    assert "Roll back" in str(result.results["deployment_reviewer"].result)
    assert "DB timeouts" in str(models["deployment_reviewer"].calls[0].messages)  # shared context
