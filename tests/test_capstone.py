"""Capstone: the production support agent, end to end, offline.

Each request builds a fresh agent, so the scripted models are handed out in order by a
small queue (one ScriptedModel per request).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

import pytest
from fastapi.testclient import TestClient
from strands.storage import LocalFileStorage

from course_common import ScriptedModel, ToolCall
from support_agent import (
    ApprovalDecision,
    AppSettings,
    Caller,
    ChatRequest,
    InMemoryShopRepository,
    SupportService,
)
from support_agent.api import create_app

ASHA = Caller(user_id="user-asha", customer_id="C-1001")
BEN = Caller(user_id="user-ben", customer_id="C-1002")
SUPERVISOR = Caller(user_id="sup-1", customer_id="STAFF", roles=frozenset({"supervisor"}))

LIST = ToolCall("list_my_orders")
SKILL = ToolCall("skills", {"skill_name": "refund-requests"})


def refund(order: str, amount: float) -> ToolCall:
    return ToolCall(
        "request_refund", {"order_id": order, "amount": amount, "reason": "arrived broken"}
    )


class Harness:
    def __init__(self, tmp_path, **settings) -> None:
        self.repo = InMemoryShopRepository.demo()
        self.models: deque[ScriptedModel] = deque()
        self.used: list[ScriptedModel] = []
        self.service = SupportService(
            AppSettings(json_logs=False, **settings),
            self.repo,
            model_factory=self._next_model,
            storage=LocalFileStorage(str(tmp_path / "sessions")),
        )

    def script(self, *turns) -> None:
        self.models.append(ScriptedModel(list(turns)))

    def _next_model(self) -> ScriptedModel:
        model = self.models.popleft() if self.models else ScriptedModel(default_text="ok")
        self.used.append(model)
        return model

    def tool_results(self, model_index: int = -1) -> list[str]:
        model = self.used[model_index]
        last = model.calls[-1].messages
        return [str(b["toolResult"]) for m in last for b in m["content"] if "toolResult" in b]


@pytest.fixture
def h(tmp_path) -> Harness:
    return Harness(tmp_path)


def chat(h: Harness, caller: Caller, message: str, conversation: str = "conv-0001"):
    return h.service.chat(caller, ChatRequest(conversation_id=conversation, message=message))


def test_small_refund_completes_after_listing_orders(h):
    h.script(SKILL, LIST, refund("ORD-5544", 19.99), "Done: refund RF-00001, 3-5 business days.")
    response = chat(h, ASHA, "Refund my phone case, it broke. Yes, go ahead.")
    assert response.status == "completed"
    assert h.repo.refunds["ORD-5544"].amount == 19.99


def test_refund_before_listing_orders_is_guided(h):
    h.script(refund("ORD-5544", 19.99), LIST, refund("ORD-5544", 19.99), "Refunded.")
    chat(h, ASHA, "refund ORD-5544")
    first_result = str(h.used[0].calls[1].messages[-1])
    assert "list_my_orders first" in first_result
    assert "ORD-5544" in h.repo.refunds  # second attempt, after listing, went through


def test_customer_cannot_touch_another_customers_order(h):
    h.script(LIST, refund("ORD-6001", 10), "I couldn't find that order.")
    response = chat(h, ASHA, "refund ORD-6001")  # belongs to Ben
    assert response.status == "completed"
    assert "ORD-6001" not in h.repo.refunds
    assert "was not found for this customer" in str(h.used[0].calls[-1].messages)


def test_large_refund_waits_for_supervisor_then_resumes(h):
    h.script(LIST, refund("ORD-5521", 79.99))
    paused = chat(h, ASHA, "Refund my headphones please, yes I confirm.")
    assert paused.status == "needs_approval" and "ORD-5521" not in h.repo.refunds
    question = paused.approvals[0].question
    assert "79.99" in question and "ORD-5521" in question

    h.script("Approved: refund RF-00001 is on its way, 3-5 business days.")
    decision = ApprovalDecision(
        user_id="user-asha",
        conversation_id="conv-0001",
        interrupt_id=paused.approvals[0].interrupt_id,
        approved=True,
    )
    resumed = h.service.decide(SUPERVISOR, decision)  # a different request, a new agent instance

    assert resumed.status == "completed"
    assert h.repo.refunds["ORD-5521"].amount == 79.99


def test_rejected_approval_means_no_refund(h):
    h.script(LIST, refund("ORD-5521", 79.99))
    paused = chat(h, ASHA, "refund headphones, yes")
    h.script("The refund was not approved; I've noted it.")
    decision = ApprovalDecision(
        user_id="user-asha",
        conversation_id="conv-0001",
        interrupt_id=paused.approvals[0].interrupt_id,
        approved=False,
    )
    assert h.service.decide(SUPERVISOR, decision).status == "completed"
    assert h.repo.refunds == {}


def test_only_supervisors_can_approve(h):
    decision = ApprovalDecision(
        user_id="user-asha", conversation_id="conv-0001", interrupt_id="x", approved=True
    )
    with pytest.raises(PermissionError):
        h.service.decide(ASHA, decision)


def test_refund_over_hard_limit_is_denied(h):
    h.script(LIST, refund("ORD-6002", 899.00), "This needs a manager; I've escalated it.")
    chat(h, BEN, "refund my speakers, yes")
    assert h.repo.refunds == {}
    assert "need a manager" in str(h.used[0].calls[-1].messages)


def test_card_numbers_never_reach_the_model(h):
    h.script("I've removed the card number. Never share it here.")
    chat(h, ASHA, "my card 4111 1111 1111 1111 was charged twice")
    assert "4111" not in str(h.used[0].calls[0].messages)


def test_conversation_history_persists_between_requests(h):
    h.script("Hi Asha!")
    chat(h, ASHA, "hello, I'm new here")
    h.script("You said hello.")
    chat(h, ASHA, "what did I say first?")
    assert "hello, I'm new here" in str(h.used[1].calls[0].messages)


def test_conversations_are_private_per_user(h):
    h.script("Noted your secret.")
    chat(h, ASHA, "my secret word is pineapple", conversation="shared-id-123")
    h.script("Hello Ben.")
    chat(h, BEN, "hi", conversation="shared-id-123")  # same conversation id, different user
    assert "pineapple" not in str(h.used[1].calls[0].messages)


def test_turn_limit_maps_to_budget_exceeded(tmp_path):
    h = Harness(tmp_path, max_turns=2)
    h.script(LIST, LIST, LIST, "never")
    assert chat(h, ASHA, "loop").status == "budget_exceeded"


def test_same_conversation_is_busy_while_running(h):
    class SlowModel(ScriptedModel):
        async def stream(self, *args, **kwargs):
            import asyncio

            await asyncio.sleep(0.5)
            async for event in super().stream(*args, **kwargs):
                yield event

    h.models.append(SlowModel(["first"]))
    results: dict[str, Any] = {}
    worker = threading.Thread(target=lambda: results.setdefault("a", chat(h, ASHA, "one")))
    worker.start()
    time.sleep(0.15)
    results["b"] = chat(h, ASHA, "two")
    worker.join()
    assert results["a"].status == "completed" and results["b"].status == "busy"


def test_http_api_requires_identity_and_returns_typed_responses(h):
    client = TestClient(create_app(h.service))
    body = {"conversation_id": "conv-0009", "message": "hi"}

    assert client.post("/v1/chat", json=body).status_code == 422  # no identity headers
    assert client.get("/healthz").json() == {"status": "ok"}

    h.script("Hello!")
    ok = client.post(
        "/v1/chat", json=body, headers={"X-User-Id": "user-asha", "X-Customer-Id": "C-1001"}
    )
    assert ok.status_code == 200 and ok.json()["status"] == "completed"

    approval = {
        "user_id": "user-asha",
        "conversation_id": "conv-0009",
        "interrupt_id": "x",
        "approved": True,
    }
    denied = client.post(
        "/v1/approvals",
        json=approval,
        headers={"X-User-Id": "user-asha", "X-Customer-Id": "C-1001"},
    )
    assert denied.status_code == 403
