"""
24-hour debug stamping system
Adds identity and processing mode to all outbound messages
"""

import os
import logging

logger = logging.getLogger(__name__)

DEBUG_MODE = os.getenv("FB_DEBUG_MODE", "1") == "1"

def stamp_reply(text: str, job: dict, mode: str) -> str:
    """
    Add 24-hour debug stamp to message
    
    Args:
        text: Original message text
        job: Background job containing psid_hash
        mode: Processing mode (AI, STD, FBK, ERR)
        
    Returns:
        Message with debug stamp if debug mode enabled
    """
    if not DEBUG_MODE:
        return text
    
    psid_hash = job.get("psid_hash", "unknown")[:8]
    debug_info = f"pong | psid_hash={psid_hash}... | mode={mode}"
    
    return f"{text}\n\n{debug_info}"

def send_reply(job: dict, text: str, mode: str = "STD"):
    """
    Send stamped reply via Facebook API
    
    Args:
        job: Background job containing psid and psid_hash
        text: Message text to send
        mode: Processing mode for debug stamp
    """
    try:
        from utils.facebook_handler import send_message
    except ImportError:
        # Fallback for testing - in production this would use the real Facebook API
        from utils.facebook_integration import send_facebook_message as send_message
    
    stamped_message = stamp_reply(text, job, mode)
    
    try:
        result = send_message(job["psid"], stamped_message)
        logger.info(f"send_api ok | mode={mode} | psid_hash={job.get('psid_hash', 'unknown')[:12]}...")
        return result
    except Exception as e:
        logger.error(f"send_api failed | mode={mode} | error={e}")
        raise