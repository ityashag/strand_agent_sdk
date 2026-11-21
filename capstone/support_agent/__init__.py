"""Capstone: a production customer-support agent built with the Strands Agents SDK."""

from support_agent.agent_factory import create_agent
from support_agent.config import AppSettings, get_settings
from support_agent.data import InMemoryShopRepository, ShopRepository
from support_agent.service import (
    ApprovalDecision,
    Caller,
    ChatRequest,
    ChatResponse,
    SupportService,
)

__all__ = [
    "AppSettings",
    "ApprovalDecision",
    "Caller",
    "ChatRequest",
    "ChatResponse",
    "InMemoryShopRepository",
    "ShopRepository",
    "SupportService",
    "create_agent",
    "get_settings",
]
