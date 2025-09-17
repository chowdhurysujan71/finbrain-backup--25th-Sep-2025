from utils.identity import user_hash_from_session_user_id
from utils.production_router import route_message
from utils import background_processor  # optional, see Mode A/B below
import uuid

def route_web_text(session_user_id: str, text: str, rid: str | None = None, mode: str = "sync"):
    user_hash = user_hash_from_session_user_id(session_user_id)
    rid = rid or uuid.uuid4().hex[:12]

    if mode == "enqueue":  # Mode B: reuse thread pool and identical timeouts
        return background_processor.enqueue_message_web(rid=rid, user_hash=user_hash, text=text)
    else:  # Mode A: sync path that calls the same production router
        # IMPORTANT: call the same production router as Messenger
        return route_message(text=text, user_hash=user_hash, rid=rid, channel="web")