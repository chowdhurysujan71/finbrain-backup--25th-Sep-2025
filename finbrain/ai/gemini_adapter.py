"""
Gemini AI adapter with single process() entrypoint
"""

import os
import logging
from typing import Dict, Any, Optional

from .contracts import InboundMessage, AIContext, AIResult

logger = logging.getLogger(__name__)

class GeminiAdapter:
    """Gemini AI adapter with standardized interface"""
    
    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.enabled = bool(self.api_key and os.environ.get("AI_ENABLED", "false").lower() == "true")
        logger.info(f"GeminiAdapter initialized: enabled={self.enabled}")
    
    def process(self, message: InboundMessage, context: AIContext) -> AIResult:
        """
        Main AI processing entrypoint
        """
        if not self.enabled:
            return {
                "reply_text": "AI is currently disabled",
                "intent": "fallback",
                "category": None,
                "amount": None,
                "confidence": 0.0,
                "intents": ["fallback"]
            }
        
        # TODO: Implement actual Gemini API calls
        return {
            "reply_text": f"Processed: {message['text'][:50]}...",
            "intent": "log_expense",
            "category": "uncategorized",
            "amount": 0.0,
            "confidence": 0.8,
            "intents": ["log_expense"]
        }
    
    def phrase_summary(self, summary: Dict[str, Any], message: Optional[InboundMessage] = None, context: Optional[AIContext] = None) -> AIResult:
        """
        Shim for summary phrasing - maintains compatibility
        """
        total = summary.get("total", 0)
        currency = summary.get("currency", "BDT")
        count = summary.get("count", 0)
        
        if count == 0:
            text = "No expenses found in the selected period."
        elif count == 1:
            text = f"You spent {total} {currency} on 1 expense."
        else:
            text = f"You spent {total} {currency} across {count} expenses."
        
        return {
            "reply_text": text,
            "intent": "summary",
            "category": None,
            "amount": float(total),
            "confidence": 1.0,
            "intents": ["summary"]
        }