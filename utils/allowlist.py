"""
Development PSID allowlist for E2E testing
Only active in non-production environments
"""
import os
from typing import Set

# Load dev PSIDs from environment variable (comma-separated)
DEV_PSIDS: set[str] = set(filter(None, os.getenv("DEV_PSIDS", "").split(",")))

def is_dev_psid(psid: str) -> bool:
    """
    Check if PSID is in the dev allowlist
    Only used in non-production environments
    """
    return psid in DEV_PSIDS

def is_allowlist_active() -> bool:
    """Check if allowlist is active (non-production only)"""
    return os.getenv("ENV") != "production"

def get_allowlist_size() -> int:
    """Get number of PSIDs in allowlist"""
    return len(DEV_PSIDS)