from utils.identity import user_hash_from_session_user_id
from utils.production_router import production_router
from utils.background_processor import background_processor
import uuid

def route_web_text(session_user_id: str, text: str, rid: str | None = None, mode: str = "sync"):
    user_hash = user_hash_from_session_user_id(session_user_id)
    rid = rid or uuid.uuid4().hex[:12]

    if mode == "enqueue":  # Mode B: reuse thread pool and identical timeouts
        return background_processor.enqueue_message_web(rid=rid, user_hash=user_hash, text=text)
    else:  # Mode A: sync path that calls the same production router as Messenger
        # IMPORTANT: call the same production router instance with correct signature  
        response_text, intent, category, amount = production_router.route_message(text, user_hash, rid, channel="web")
        
        # Return structured response for web UI
        return {
            "messages": [{"role": "assistant", "content": response_text}],
            "events": [],
            "recent": []
        }