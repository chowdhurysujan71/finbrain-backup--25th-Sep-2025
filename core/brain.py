"""
FinBrain Core: Unified Message Processing Brain
One brain, two doors - handles all user messages and returns clean text reply + optional structured data
"""

import logging
import time
from typing import Dict, Any
from utils.identity import psid_hash
from utils.timebox import call_with_timeout_fallback

logger = logging.getLogger(__name__)

def process_user_message(uid: str, text: str) -> Dict[str, Any]:
    """
    Unified message processing brain - handles user messages and returns consistent response format
    
    Args:
        uid: User identifier (unhashed PSID or user ID)
        text: User message text
        
    Returns:
        Dict with format: {"reply": str, "structured": {...}, "metadata": {...}}
    """
    t0 = time.time()
    
    if not text or not text.strip():
        out = {
            "reply": "I didn't receive your message. Please try again.",
            "structured": {},
            "metadata": {"error": "empty_message"}
        }
        out.setdefault("metadata", {})
        out["metadata"].update({
            "source": out["metadata"].get("source", "validation_error"),
            "latency_ms": int((time.time() - t0) * 1000),
            "uid_prefix": "anon"
        })
        return out
    
    # Normalize user ID
    user_hash = psid_hash(uid) if uid else "anon"
    
    logger.info(f"Brain processing message from {user_hash[:8]}...: '{text[:50]}...'")
    
    try:
        # Attempt to use production router (primary brain)
        result = _use_production_router(user_hash, text)
        if result:
            out = result
        else:
            # Fallback to AI adapter if router unavailable
            result = _use_fallback_ai(user_hash, text)
            if result:
                out = result
            else:
                # Last resort: simple acknowledgment
                out = {
                    "reply": "I received your message but I'm having trouble processing it right now. Please try again in a moment.",
                    "structured": {},
                    "metadata": {"source": "emergency_fallback"}
                }
                
        # Normalize user-unfriendly replies before returning
        reply = out.get("reply")
        if not reply or str(reply).strip().lower() in ("none", "null", ""):
            out["reply"] = "Got it — what would you like me to do next?"
        
        # Add consistent metadata to all responses
        out.setdefault("metadata", {})
        out["metadata"].update({
            "source": out["metadata"].get("source", "unknown"),
            "latency_ms": int((time.time() - t0) * 1000),
            "uid_prefix": user_hash[:8]
        })
        return out
        
    except Exception as e:
        logger.exception(f"Brain processing failed for {user_hash[:8]}")
        out = {
            "reply": "I'm experiencing some technical difficulties. Please try again in a moment.",
            "structured": {},
            "metadata": {"error": "brain_exception", "detail": str(e)[:100]}
        }
        out.setdefault("metadata", {})
        out["metadata"].update({
            "source": out["metadata"].get("source", "exception_fallback"),
            "latency_ms": int((time.time() - t0) * 1000),
            "uid_prefix": user_hash[:8]
        })
        return out

def _use_production_router(user_hash: str, text: str) -> Dict[str, Any]:
    """Use the production router system (primary brain)"""
    try:
        from utils.production_router import production_router
        
        logger.info(f"Using production router for {user_hash[:8]}")
        
        # Import Flask app for context (same pattern as background processor)
        from app import app
        
        # Wrap router call with Flask context and 12-second timeout
        def _router_call():
            with app.app_context():
                return production_router.route_message(user_hash, text)
        
        response_data = call_with_timeout_fallback(
            _router_call, 
            timeout_s=12.0,
            fallback_value=None
        )
        
        logger.info(f"Production router success: {str(response_data)[:100]}...")
        
        # Normalize production router response to consistent format
        if isinstance(response_data, tuple) and len(response_data) >= 2:
            # Production router returns (reply, intent, category, amount)
            reply, intent = response_data[:2]
            category = response_data[2] if len(response_data) > 2 else None
            amount = response_data[3] if len(response_data) > 3 else None
            
            structured_data = {}
            if intent:
                structured_data["intent"] = intent
            if category:
                structured_data["category"] = category
            if amount:
                structured_data["amount"] = float(amount)
                
            return {
                "reply": str(reply),
                "structured": structured_data,
                "metadata": {"source": "production_router", "intent": intent}
            }
            
        elif isinstance(response_data, dict):
            # Handle dictionary responses
            reply = response_data.get('message', response_data.get('response', response_data.get('reply', str(response_data))))
            return {
                "reply": str(reply),
                "structured": response_data.get('data', {}),
                "metadata": {"source": "production_router"}
            }
            
        else:
            # Handle string responses
            return {
                "reply": str(response_data),
                "structured": {},
                "metadata": {"source": "production_router"}
            }
            
    except (ImportError, AttributeError) as e:
        logger.info(f"Production router not available: {e}")
        return None
    except Exception as e:
        logger.warning(f"Production router failed: {e}")
        return None

def _use_fallback_ai(user_hash: str, text: str) -> Dict[str, Any]:
    """Fallback AI processing when production router unavailable"""
    try:
        # Try AI adapter
        from utils.ai_adapter_v2 import production_ai_adapter
        
        if production_ai_adapter and production_ai_adapter.enabled:
            logger.info(f"Using AI adapter fallback for {user_hash[:8]}")
            
            # Create context for AI processing
            context = {
                "user_id": user_hash,
                "message": text,
                "intent": "general_query"
            }
            
            # Wrap AI call with 10-second timeout
            def _ai_call():
                return production_ai_adapter.generate_structured_response(text, context)
            
            ai_response = call_with_timeout_fallback(
                _ai_call,
                timeout_s=10.0,
                fallback_value={"ok": False, "reason": "timeout"}
            )
            
            if ai_response.get("ok"):
                data = ai_response.get("data", {})
                return {
                    "reply": data.get("summary", "I processed your message."),
                    "structured": {
                        "key_insight": data.get("key_insight"),
                        "recommendation": data.get("recommendation"),
                        "smart_tip": data.get("smart_tip")
                    },
                    "metadata": {"source": "ai_adapter"}
                }
            else:
                logger.warning(f"AI adapter failed: {ai_response.get('reason')}")
        
        # Simple fallback response
        return {
            "reply": "I received your message. How can I help you track your expenses today?",
            "structured": {},
            "metadata": {"source": "simple_fallback"}
        }
        
    except Exception as e:
        logger.warning(f"Fallback AI failed: {e}")
        return None

# Expense-specific processing for natural language expense entry
def process_expense_message(uid: str, text: str) -> Dict[str, Any]:
    """
    Process natural language expense messages and extract structured expense data
    
    Args:
        uid: User identifier
        text: Natural language expense description
        
    Returns:
        Dict with expense data if detected, otherwise general response
    """
    result = process_user_message(uid, text)
    
    # Check if this was an expense logging intent
    if result.get("metadata", {}).get("intent") == "expense_log":
        # Add expense-specific metadata
        structured = result.get("structured", {})
        if structured.get("amount") and structured.get("category"):
            result["structured"]["is_expense"] = True
            result["structured"]["ready_to_save"] = True
    
    return result