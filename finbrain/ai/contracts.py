"""
Contracts barrel - re-exports canonical types for AI system
Single source of truth for InboundMessage, AIContext, and AIResult
"""

from typing import Any, Dict, List, Optional, TypedDict


# InboundMessage - represents an incoming message
class InboundMessage(TypedDict):
    psid_hash: str
    text: str
    mid: str
    timestamp: int

# AIContext - context data for AI processing
class AIContext(TypedDict):
    user_id: str
    history: list[dict[str, Any]]
    app_config: dict[str, Any]

# AIResult - result from AI processing
class AIResult(TypedDict):
    reply_text: str
    intent: str | None
    category: str | None 
    amount: float | None
    confidence: float | None
    intents: list[str] | None