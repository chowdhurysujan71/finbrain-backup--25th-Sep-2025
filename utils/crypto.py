"""
Unified cryptographic utilities to eliminate hash inconsistencies
"""
import hashlib
import logging

logger = logging.getLogger(__name__)

def is_sha256_hex(s: str) -> bool:
    """Check if string is a valid SHA-256 hex hash"""
    if not isinstance(s, str):
        return False
    return len(s) == 64 and all(c in '0123456789abcdef' for c in s.lower())

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
    
    # If it's already a 64-character hex string, return as-is
    if is_sha256_hex(psid_or_hash):
        return psid_or_hash.lower()
    
    # Otherwise, hash it
    result = hashlib.sha256(psid_or_hash.encode('utf-8')).hexdigest()
    
    # Strict validation in debug mode
    import os
    if os.environ.get('STRICT_IDS', 'false').lower() == 'true':
        assert is_sha256_hex(result), f"Generated hash is invalid: {result}"
    
    return result