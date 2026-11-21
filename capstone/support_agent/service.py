"""The service layer: one request in, one typed response out.

Production pattern (lesson 15): a FRESH agent per request, history loaded from the session
store, limits + deadline on every run, a per-conversation lock, and stop reasons mapped to
a small set of statuses the client can handle.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field
from strands.agent.agent_result import AgentResult
from strands.models.model import Model
from strands.storage.storage import Storage
from strands.types.exceptions import ContextWindowOverflowException, MaxTokensReachedException

from support_agent.agent_factory import create_agent
from support_agent.config import AppSettings
from support_agent.data import ShopRepository

log = logging.getLogger("support.service")

ID = r"^[A-Za-z0-9_-]{3,64}$"

Status = Literal[
    "completed", "needs_approval", "budget_exceeded", "cancelled", "blocked", "busy", "error"
]


class Caller(BaseModel):
    """Who is calling. Built by the API from a VERIFIED identity, never from the request body."""

    user_id: str = Field(pattern=ID)
    customer_id: str = Field(pattern=ID)
    roles: frozenset[str] = frozenset()


class ChatRequest(BaseModel):
    conversation_id: str = Field(pattern=ID)
    message: str = Field(min_length=1, max_length=4000)
    request_id: str | None = Field(default=None, pattern=ID)


class ApprovalDecision(BaseModel):
    user_id: str = Field(pattern=ID, description="The customer who owns the conversation")
    conversation_id: str = Field(pattern=ID)
    interrupt_id: str = Field(min_length=1, max_length=300)
    approved: bool


class PendingApproval(BaseModel):
    interrupt_id: str
    question: str


class ChatResponse(BaseModel):
    status: Status
    reply: str
    request_id: str
    stop_reason: str | None = None
    approvals: list[PendingApproval] = []
    total_tokens: int = 0


MESSAGES: dict[str, str] = {
    "budget_exceeded": "That request needs more steps than I'm allowed. Could you narrow it down?",
    "cancelled": "Sorry, that took too long. Please try again.",
    "blocked": "Sorry, I can't help with that request.",
    "busy": "I'm still working on your previous message. Please wait a moment.",
    "error": "Sorry, something went wrong on our side. Please try again.",
}


class SupportService:
    def __init__(
        self,
        settings: AppSettings,
        repo: ShopRepository,
        *,
        model_factory: Callable[[], Model] | None = None,
        storage: Storage | None = None,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.model_factory = model_factory
        self.storage = storage
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # --- public API ------------------------------------------------------------------
    def chat(self, caller: Caller, request: ChatRequest) -> ChatResponse:
        session_id = self.session_id(caller.user_id, request.conversation_id)
        owner = {"user_id": caller.user_id, "customer_id": caller.customer_id}
        return self._run(session_id, owner, request.message, request.request_id, new_owner=True)

    def decide(self, approver: Caller, decision: ApprovalDecision) -> ChatResponse:
        """A supervisor approves or rejects a paused refund. Resumes the saved run."""
        if "supervisor" not in approver.roles:
            raise PermissionError("Only supervisors can approve refunds.")
        session_id = self.session_id(decision.user_id, decision.conversation_id)
        responses = [
            {
                "interruptResponse": {
                    "interruptId": decision.interrupt_id,
                    "response": decision.approved,
                }
            }
        ]
        log.info(
            "approval_decision",
            extra={
                "fields": {
                    "session_id": session_id,
                    "approver": approver.user_id,
                    "approved": decision.approved,
                }
            },
        )
        return self._run(session_id, None, responses, None, new_owner=False)

    @staticmethod
    def session_id(user_id: str, conversation_id: str) -> str:
        # Derived from the AUTHENTICATED user: nobody can open another user's conversation.
        return f"{user_id}--{conversation_id}"

    # --- internals -------------------------------------------------------------------
    def _lock_for(self, session_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, threading.Lock())

    def _run(
        self,
        session_id: str,
        owner: dict[str, str] | None,
        prompt: Any,
        request_id: str | None,
        *,
        new_owner: bool,
    ) -> ChatResponse:
        request_id = request_id or str(uuid.uuid4())
        lock = self._lock_for(session_id)
        if not lock.acquire(blocking=False):  # one run per conversation at a time
            return ChatResponse(status="busy", reply=MESSAGES["busy"], request_id=request_id)
        try:
            model = self.model_factory() if self.model_factory else None
            agent = create_agent(
                session_id=session_id,
                settings=self.settings,
                repo=self.repo,
                model=model,
                storage=self.storage,
            )
            stored_owner = agent.state.get("owner")
            if new_owner:
                if stored_owner and stored_owner != owner:
                    raise PermissionError("Conversation belongs to another customer.")
                agent.state.set("owner", owner)  # saved with the session
            owner = stored_owner or owner
            if not owner:
                raise LookupError("Unknown conversation.")

            result = self._invoke(agent, prompt, owner, session_id, request_id)
            return self._to_response(result, request_id)
        except (ContextWindowOverflowException, MaxTokensReachedException):
            return ChatResponse(
                status="budget_exceeded", reply=MESSAGES["budget_exceeded"], request_id=request_id
            )
        except PermissionError:
            raise
        except Exception:
            # Log the failure with IDs; never return internal details to the client.
            log.exception(
                "agent_run_failed",
                extra={"fields": {"request_id": request_id, "session_id": session_id}},
            )
            return ChatResponse(status="error", reply=MESSAGES["error"], request_id=request_id)
        finally:
            lock.release()

    def _invoke(
        self, agent: Any, prompt: Any, owner: dict[str, str], session_id: str, request_id: str
    ) -> AgentResult:
        cancel = threading.Event()
        timer = threading.Timer(self.settings.deadline_seconds, cancel.set)
        timer.start()
        try:
            return agent(
                prompt,
                limits={
                    "turns": self.settings.max_turns,
                    "total_tokens": self.settings.max_total_tokens,
                },
                cancel_signal=cancel,
                invocation_state={  # identity for tools and logs; never shown to the model
                    "customer_id": owner["customer_id"],
                    "user_id": owner["user_id"],
                    "session_id": session_id,
                    "request_id": request_id,
                },
            )
        finally:
            timer.cancel()

    @staticmethod
    def _to_response(result: AgentResult, request_id: str) -> ChatResponse:
        reason = result.stop_reason
        latest = result.metrics.latest_agent_invocation
        tokens = latest.usage.get("totalTokens", 0) if latest else 0
        common: dict[str, Any] = {
            "request_id": request_id,
            "stop_reason": reason,
            "total_tokens": tokens,
        }
        if reason == "interrupt":
            approvals = [
                PendingApproval(interrupt_id=i.id, question=str(i.reason))
                for i in result.interrupts or []
            ]
            reply = (
                "Your refund needs a quick approval from a supervisor. We'll update you shortly."
            )
            return ChatResponse(status="needs_approval", reply=reply, approvals=approvals, **common)
        if reason in ("end_turn", "stop_sequence"):
            return ChatResponse(status="completed", reply=str(result).strip(), **common)
        status: Status = (
            "budget_exceeded"
            if reason.startswith("limit_")
            else "cancelled"
            if reason == "cancelled"
            else "blocked"
            if reason in ("guardrail_intervened", "content_filtered")
            else "error"
        )
        log.warning(
            "agent_run_stopped", extra={"fields": {"request_id": request_id, "stop_reason": reason}}
        )
        return ChatResponse(status=status, reply=MESSAGES[status], **common)
