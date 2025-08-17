"""
Unified cryptographic utilities to eliminate hash inconsistencies
"""
import hashlib
import logging

logger = logging.getLogger(__name__)

def ensure_hashed(psid_or_hash: str) -> str:
    """
    Ensure we have a consistently hashed user identifier
    
    Args:
        psid_or_hash: Either a raw PSID or already-hashed identifier
        
    Returns:
        SHA-256 hash of the identifier
    """
    if not psid_or_hash:
        raise ValueError("psid_or_hash cannot be empty")
    
    # If it's already a 64-character hex string, assume it's hashed
    if len(psid_or_hash) == 64 and all(c in '0123456789abcdef' for c in psid_or_hash.lower()):
        return psid_or_hash.lower()
    
    # Otherwise, hash it
    return hashlib.sha256(psid_or_hash.encode('utf-8')).hexdigest()