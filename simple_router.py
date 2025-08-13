"""
Streamlined message router: webhook -> router -> (AI | deterministic)
Single path with rate limiting and telemetry
"""
import time
import logging
from typing import Tuple, Optional, Dict, Any

from flags import is_ai_enabled
from ai_adapter import generate
from utils.parser import parse_expense
from utils.categories import categorize_expense
from utils.security import hash_psid
from utils.ai_limiter import advanced_ai_limiter

logger = logging.getLogger(__name__)

class SimpleRouter:
    """Streamlined router with AI-first approach and deterministic fallback"""
    
    def __init__(self):
        self.stats = {
            "total_messages": 0,
            "ai_messages": 0,
            "deterministic_messages": 0,
            "rate_limited_messages": 0
        }
        logger.info("Simple router initialized")
    
    def route_message(self, text: str, psid: str) -> Tuple[str, Dict[str, Any]]:
        """
        Route message: AI-first with deterministic fallback
        Returns: (response_text, metadata)
        """
        start_time = time.time()
        psid_hash = hash_psid(psid)
        
        self.stats["total_messages"] += 1
        
        # Check rate limiting first
        if not advanced_ai_limiter.allow_request(psid_hash):
            self.stats["rate_limited_messages"] += 1
            response = self._handle_deterministic(text, psid_hash)
            response["rate_limited"] = True
            response["reason"] = "rate_limited"
            return response["text"], response
        
        # Try AI first if enabled
        if is_ai_enabled():
            ai_response = self._try_ai(text, psid_hash)
            if ai_response["ok"]:
                self.stats["ai_messages"] += 1
                return ai_response["text"], {
                    "route": "ai",
                    "latency_ms": ai_response["latency_ms"],
                    "rate_limited": False
                }
        
        # Fallback to deterministic
        self.stats["deterministic_messages"] += 1
        response = self._handle_deterministic(text, psid_hash)
        response["route"] = "deterministic"
        response["rate_limited"] = False
        
        return response["text"], response
    
    def _try_ai(self, text: str, psid_hash: str) -> Dict[str, Any]:
        """Try AI processing with expense context"""
        # Parse expense first for context
        parsed = parse_expense(text)
        
        if parsed["amount"] and parsed["description"]:
            # Expense logging request
            prompt = f"User wants to log expense: {parsed['amount']} for {parsed['description']}. Categorize and confirm briefly."
        elif "summary" in text.lower():
            prompt = f"User asked: {text}. Provide a brief expense summary request acknowledgment."
        else:
            prompt = f"User message: {text}. Respond helpfully about expense tracking."
        
        return generate(prompt)
    
    def _handle_deterministic(self, text: str, psid_hash: str) -> Dict[str, Any]:
        """Handle message deterministically"""
        parsed = parse_expense(text)
        
        if parsed["amount"] and parsed["description"]:
            # Log expense deterministically
            category = categorize_expense(parsed["description"])
            response_text = f"Logged ${parsed['amount']:.2f} for {parsed['description']} (category: {category})"
            
            return {
                "text": response_text,
                "intent": "log_expense",
                "amount": parsed["amount"],
                "category": category,
                "description": parsed["description"]
            }
        
        elif "summary" in text.lower():
            return {
                "text": "Here's your expense summary: Total logged expenses available in dashboard.",
                "intent": "summary"
            }
        
        else:
            return {
                "text": "I can help you log expenses. Try: 'log 25 coffee' or ask for 'summary'",
                "intent": "help"
            }
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get routing telemetry"""
        return {
            "stats": self.stats.copy(),
            "ai_enabled": is_ai_enabled(),
            "limiter_stats": advanced_ai_limiter.get_stats()
        }

# Global router instance
simple_router = SimpleRouter()