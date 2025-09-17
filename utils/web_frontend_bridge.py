"""
Web Frontend Bridge - Unified entry point for web chat requests
Routes web requests through the same production pipeline as Messenger
"""

from utils.identity import user_hash_from_session_user_id
import uuid
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def route_web_text(session_user_id: str, text: str, rid: Optional[str] = None, mode: str = "sync"):
    """
    Route web text through the same production pipeline as Messenger
    
    Args:
        session_user_id: User ID from web session
        text: User message text
        rid: Optional request ID (auto-generated if not provided)
        mode: "sync" for direct routing, "enqueue" for background processing
        
    Returns:
        Response in format compatible with web UI
    """
    user_hash = user_hash_from_session_user_id(session_user_id)
    rid = rid or uuid.uuid4().hex[:12]

    if mode == "enqueue":  # Mode B: reuse thread pool and identical timeouts
        return enqueue_message_web(rid=rid, user_hash=user_hash, text=text)
    else:  # Mode A: sync path that calls the same production router
        # IMPORTANT: call the same production router as Messenger
        try:
            from utils.production_router import route_message
            response_text, intent, category, amount = route_message(text=text, user_hash=user_hash, rid=rid, channel="web")
            
            # Convert to web UI format (same structure as current chat endpoint)
            return {
                "messages": [{
                    "role": "assistant",
                    "content": response_text
                }],
                "events": [],
                "recent": []
            }
        except Exception as e:
            logger.error(f"Web bridge routing error: {e}")
            return {
                "messages": [{
                    "role": "assistant", 
                    "content": "I'm here to help! Please try again."
                }],
                "events": [],
                "recent": []
            }

def enqueue_message_web(rid: str, user_hash: str, text: str):
    """
    Enqueue web message for background processing (Mode B support)
    
    Args:
        rid: Request ID
        user_hash: Hashed user identifier
        text: Message text
        
    Returns:
        Queue confirmation response
    """
    # mirrors enqueue_message(... psid ...) but skips PSID → hash, since we already have the hash
    job = {"rid": rid, "user_hash": user_hash, "text": text, "channel": "web"}
    
    try:
        # Add to background processor queue if available
        from utils.background_processor import background_processor
        # Note: This would require extending background_processor to handle web jobs
        # For now, fallback to sync mode
        logger.warning("Background enqueue for web not yet implemented, falling back to sync")
        return route_web_text(user_hash, text, rid, mode="sync")
    except Exception as e:
        logger.error(f"Web enqueue error: {e}")
        return {"ok": False, "error": str(e)}