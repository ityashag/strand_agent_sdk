"""HTTP API (FastAPI). Run locally:

    uv run uvicorn support_agent.api:build_app --factory --port 8000

    curl -s localhost:8000/v1/chat -H 'content-type: application/json' \
      -H 'X-User-Id: user-asha' -H 'X-Customer-Id: C-1001' \
      -d '{"conversation_id": "conv-0001", "message": "What did I order?"}'

AUTH NOTE: the X-User-Id / X-Customer-Id / X-Roles headers are a DEMO stand-in. In production,
verify a JWT (Cognito, Okta, AgentCore Identity...) in `get_caller` and read the IDs and roles
from its claims. Never trust identity values sent by the client.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import ValidationError

from support_agent.config import get_settings
from support_agent.data import InMemoryShopRepository
from support_agent.observability import configure_logging, setup_tracing
from support_agent.service import (
    ApprovalDecision,
    Caller,
    ChatRequest,
    ChatResponse,
    SupportService,
)


def create_app(service: SupportService) -> FastAPI:
    app = FastAPI(title="Support agent", version="1.0.0")

    def get_caller(
        x_user_id: str = Header(...),
        x_customer_id: str = Header(...),
        x_roles: str = Header(default=""),
    ) -> Caller:
        try:
            return Caller(
                user_id=x_user_id,
                customer_id=x_customer_id,
                roles=frozenset(r.strip() for r in x_roles.split(",") if r.strip()),
            )
        except ValidationError as error:
            raise HTTPException(status_code=401, detail="invalid identity") from error

    @app.post("/v1/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, caller: Caller = Depends(get_caller)) -> ChatResponse:
        # A plain `def` endpoint runs in a worker thread, so the blocking agent call
        # doesn't block the event loop.
        try:
            return service.chat(caller, body)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

    @app.post("/v1/approvals", response_model=ChatResponse)
    def approve(body: ApprovalDecision, caller: Caller = Depends(get_caller)) -> ChatResponse:
        try:
            return service.decide(caller, body)
        except PermissionError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def build_app() -> FastAPI:
    """App factory for uvicorn: `uvicorn support_agent.api:build_app --factory`."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.json_logs)
    setup_tracing()
    # Replace InMemoryShopRepository with your real order-system adapter.
    return create_app(SupportService(settings, InMemoryShopRepository.demo()))
