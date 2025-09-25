"""
Deterministic hashing utilities
"""
import hashlib


def ensure_hashed(input_str):
    """Ensure input is hashed deterministically"""
    if input_str is None:
        return 'anonymous'
    return hashlib.sha256(str(input_str).encode()).hexdigest()[:32]
