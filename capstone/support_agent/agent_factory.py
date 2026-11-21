"""Build one fully configured agent. Every production setting lives here, in one place."""

from __future__ import annotations

from pathlib import Path

from strands import Agent, AgentSkills, ModelRetryStrategy
from strands.models import ModelRouter
from strands.models.model import Model
from strands.session import SnapshotSessionManager
from strands.storage import LocalFileStorage, S3Storage
from strands.storage.storage import Storage
from strands.tools.executors import SequentialToolExecutor

from support_agent.config import AppSettings
from support_agent.data import ShopRepository
from support_agent.models import build_model
from support_agent.observability import AuditHook
from support_agent.policies import (
    NoTimelinePromises,
    RedactPayments,
    RefundApproval,
    RefundWorkflow,
)
from support_agent.tools import SupportTools

SKILLS_DIR = Path(__file__).with_name("skills")

SYSTEM_PROMPT = """You are the customer support agent of an electronics shop.
You always act for the signed-in customer only; you cannot see other customers.
- Use the tools for every fact about orders and refunds. Never invent orders, amounts or dates.
- Load the matching skill and follow it for refunds and order questions.
- Ask before any refund and act only after a clear yes.
- If a tool fails, say so honestly and offer escalate_to_human.
- Be brief and friendly. Do not promise timelines except "3-5 business days" for refunds."""


def session_storage(settings: AppSettings) -> Storage:
    if settings.session_bucket:
        return S3Storage(bucket=settings.session_bucket, prefix=settings.session_prefix)
    return LocalFileStorage(settings.session_dir)


def create_agent(
    *,
    session_id: str,
    settings: AppSettings,
    repo: ShopRepository,
    model: Model | ModelRouter | None = None,
    storage: Storage | None = None,
) -> Agent:
    return Agent(
        name="support-agent",
        description="Customer support for orders and refunds.",
        agent_id="support-agent",
        model=model or build_model(settings),
        system_prompt=SYSTEM_PROMPT,
        tools=SupportTools(repo).all(),
        # Refund after listing orders: keep side effects in the order the model chose.
        tool_executor=SequentialToolExecutor(),
        plugins=[
            AgentSkills(skills=[str(SKILLS_DIR)], strict=True),  # lesson 08
            RefundWorkflow(),  # lesson 09 (steering)
            NoTimelinePromises(),
        ],
        interventions=[  # lesson 09/16: cheap, decisive checks first
            RedactPayments(),
            RefundApproval(settings.refund_auto_approve_limit, settings.refund_hard_limit),
        ],
        hooks=[AuditHook()],  # lesson 07/17
        session_manager=SnapshotSessionManager(  # lesson 11
            session_id=session_id,
            storage=storage or session_storage(settings),
            save_latest_on="invocation",
        ),
        context_manager="auto",  # lesson 10
        retry_strategy=ModelRetryStrategy(
            max_attempts=3, initial_delay=2, max_delay=20
        ),  # lesson 15
        trace_attributes={"session.id": session_id, "service.name": "support-agent"},  # lesson 17
        callback_handler=None,  # lesson 06: a server never prints
    )
