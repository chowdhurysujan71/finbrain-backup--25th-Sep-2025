"""
Centralized user ID management and normalization
Single source of truth for user identification across the system
"""
from utils.crypto import ensure_hashed

def resolve_user_id(*, psid: str = None, psid_hash: str = None) -> str:
    """
    Centralized user ID resolution - single entry point for all user identification
    
    Args:
        psid: Raw PSID (will be hashed)
        psid_hash: Already hashed PSID (will be validated and passed through)
        
    Returns:
        Normalized user ID (SHA-256 hash)
        
    Raises:
        ValueError: If neither psid nor psid_hash is provided
    """
    if not (psid or psid_hash):
        raise ValueError("Provide psid or psid_hash")
    return ensure_hashed(psid or psid_hash)