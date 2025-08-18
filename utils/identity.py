"""
Single Source of Identity - hash once, carry through
Centralized extraction + hashing to prevent identity fragmentation
"""
import os
import hashlib

ID_SALT = os.getenv("ID_SALT")
if not ID_SALT:
    raise RuntimeError("ID_SALT missing")

def extract_sender_psid(event: dict) -> str | None:
    """
    Only messages/postbacks create a user context
    """
    try:
        m = event.get("entry", [{}])[0].get("messaging", [{}])[0]
        if "message" in m or "postback" in m:
            return m.get("sender", {}).get("id")
        return None  # delivery/read/etc.
    except (IndexError, KeyError):
        return None

def psid_hash(psid: str) -> str:
    """
    Generate consistent hash using mandatory salt
    """
    return hashlib.sha256(f"{ID_SALT}|{psid}".encode()).hexdigest()

# Legacy alias for backward compatibility
psid_from_event = extract_sender_psid