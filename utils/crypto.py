"""
Unified cryptographic utilities to eliminate hash inconsistencies
"""
import hashlib
import logging
from utils.identity import ensure_hashed as identity_ensure_hashed

logger = logging.getLogger(__name__)

def is_sha256_hex(s: str) -> bool:
    """Check if string is a valid SHA-256 hex hash"""
    if not isinstance(s, str):
        return False
    return len(s) == 64 and all(c in '0123456789abcdef' for c in s.lower())

def ensure_hashed(psid_or_hash: str) -> str:
    """
    Ensure we have a consistently hashed user identifier
    
    CRITICAL: This function now delegates to utils.identity.ensure_hashed() 
    to ensure ALL hashing uses the same salted method: SHA256(ID_SALT|id)
    
    Args:
        psid_or_hash: Either a raw PSID or already-hashed identifier
        
    Returns:
        SHA-256 hash of the identifier using consistent salted method
    """
    if not psid_or_hash:
        raise ValueError("psid_or_hash cannot be empty")
    
    # Delegate to identity module for consistent salted hashing
    # This fixes the hash inconsistency that broke reconciliation
    return identity_ensure_hashed(psid_or_hash)