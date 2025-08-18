"""Canonical identity management for FinBrain users"""
import hashlib
import os

_ID_SALT = os.getenv("ID_SALT", "CHANGE_ME")

def psid_hash(raw_psid: str) -> str:
    """Generate canonical hash for Facebook PSID using salted SHA-256"""
    return hashlib.sha256((raw_psid + _ID_SALT).encode()).hexdigest()