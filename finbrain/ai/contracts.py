"""
Contracts barrel - re-exports canonical types for AI system
Single source of truth for InboundMessage, AIContext, and AIResult
"""

from typing import TypedDict, List, Dict, Any, Optional

# InboundMessage - represents an incoming message
class InboundMessage(TypedDict):
    psid_hash: str
    text: str
    mid: str
    timestamp: int

# AIContext - context data for AI processing
class AIContext(TypedDict):
    user_id: str
    history: List[Dict[str, Any]]
    app_config: Dict[str, Any]

# AIResult - result from AI processing
class AIResult(TypedDict):
    reply_text: str
    intent: Optional[str]
    category: Optional[str] 
    amount: Optional[float]
    confidence: Optional[float]
    intents: Optional[List[str]]