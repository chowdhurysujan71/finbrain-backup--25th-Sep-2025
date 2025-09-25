"""
Centralized user ID management and normalization
Single source of truth for user identification across the system
"""
from utils.identity import psid_hash


def resolve_user_id(psid: str) -> str:
    """
    Centralized user ID resolution using canonical identity
    
    Args:
        psid: Raw PSID (will be hashed using canonical salt)
        
    Returns:
        Canonical user ID hash (SHA-256 with salt)
    """
    return psid_hash(psid)