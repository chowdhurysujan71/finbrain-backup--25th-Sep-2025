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

def ensure_hashed(user_identifier: str) -> str:
    """
    Ensure user identifier is properly hashed
    
    Args:
        user_identifier: Raw PSID or already hashed identifier
        
    Returns:
        Hashed user identifier
    """
    if not user_identifier:
        raise ValueError("User identifier cannot be empty")
    
    # If already looks like a hash (64 hex chars), return as-is
    if len(user_identifier) == 64 and all(c in '0123456789abcdef' for c in user_identifier.lower()):
        return user_identifier
    
    # Otherwise, hash it
    return psid_hash(user_identifier)