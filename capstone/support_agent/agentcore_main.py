"""Amazon Bedrock AgentCore Runtime entrypoint for the same service.

    python -m support_agent.agentcore_main        # serves POST /invocations and GET /ping on :8080

Payload: {"conversation_id": "conv-0001", "message": "..."}
Identity: configure AgentCore inbound auth (JWT/OAuth or IAM) and pass the verified user and
customer IDs to the runtime from your backend. This demo reads them from the payload ONLY
when SUPPORT_ALLOW_PAYLOAD_IDENTITY=true (local testing); otherwise it refuses.
"""

from __future__ import annotations

import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.runtime.context import RequestContext
from pydantic import ValidationError

from support_agent.config import get_settings
from support_agent.data import InMemoryShopRepository
from support_agent.observability import configure_logging, setup_tracing
from support_agent.service import Caller, ChatRequest, SupportService

settings = get_settings()
configure_logging(settings.log_level, settings.json_logs)
setup_tracing()
service = SupportService(settings, InMemoryShopRepository.demo())
app = BedrockAgentCoreApp()
ALLOW_PAYLOAD_IDENTITY = os.environ.get("SUPPORT_ALLOW_PAYLOAD_IDENTITY", "").lower() == "true"


@app.entrypoint
def invoke(payload: dict[str, Any], context: RequestContext) -> dict[str, Any]:
    if not ALLOW_PAYLOAD_IDENTITY:
        return {"status": "error", "reply": "identity not configured"}
    try:
        caller = Caller(user_id=payload["user_id"], customer_id=payload["customer_id"])
        request = ChatRequest(
            conversation_id=payload["conversation_id"], message=payload["message"]
        )
    except (KeyError, ValidationError):
        return {"status": "error", "reply": "invalid request"}
    return service.chat(caller, request).model_dump()


if __name__ == "__main__":
    app.run()
