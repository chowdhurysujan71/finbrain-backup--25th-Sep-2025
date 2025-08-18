"""
Canonical Identity System for FinBrain
Single source of truth for user identification across the system
"""
import hashlib
import os

# Crash if ID_SALT is missing - prevents workers from using different values
ID_SALT = os.environ.get("ID_SALT")
if not ID_SALT:
    raise RuntimeError("ID_SALT environment variable is required for identity consistency")

def psid_from_event(evt: dict) -> str | None:
    """
    Extract PSID from Facebook webhook event - ONLY for messages & postbacks
    
    Args:
        evt: Facebook webhook event dictionary
        
    Returns:
        sender.id if this is a message/postback event, None otherwise
    """
    try:
        messaging = evt.get("entry", [{}])[0].get("messaging", [{}])[0]
        
        # Only process message and postback events for identity
        if "message" in messaging or "postback" in messaging:
            return messaging.get("sender", {}).get("id")
        
        # Ignore delivery/read events - they don't need identity processing
        return None
    except (IndexError, KeyError, TypeError):
        return None

def psid_hash(raw_psid: str) -> str:
    """
    Generate canonical SHA-256 hash for a PSID using environment salt
    
    Args:
        raw_psid: Raw Facebook PSID (sender.id only)
        
    Returns:
        SHA-256 hash using ID_SALT environment variable
    """
    combined = f"{ID_SALT}|{raw_psid}"
    return hashlib.sha256(combined.encode()).hexdigest()