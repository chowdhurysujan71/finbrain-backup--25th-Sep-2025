"""
Feature Flags for FinBrain - PHASE 7 CONSOLIDATION SHIM
This module now delegates to the unified flags system for single source of truth
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("finbrain.feature_flags")

# PHASE 7: Import unified flags system
# Import centralized config for backward compatibility
from utils.config import FEATURE_FLAGS_VERSION
from utils.flags import unified_flags


def is_smart_nlp_enabled(psid_hash: str | None = None) -> bool:
    """
    PHASE 7: Delegates to unified flags system
    """
    return unified_flags.is_smart_nlp_enabled(psid_hash)

def is_smart_tone_enabled(psid_hash: str | None = None) -> bool:
    """
    PHASE 7: Delegates to unified flags system
    """
    return unified_flags.is_smart_tone_enabled(psid_hash)

def is_smart_corrections_enabled(psid_hash: str | None = None) -> bool:
    """
    PHASE 7: Delegates to unified flags system
    """
    return unified_flags.is_smart_corrections_enabled(psid_hash)

def feature_enabled(*_args, **_kwargs) -> bool:
    """
    All features are now permanently enabled.
    Single source for feature checks - always returns True.
    
    Kept for easy rollback if needed, but all features are on.
    
    Returns:
        Always True - all features permanently enabled
    """
    return True

def get_canary_status():
    """
    Get current status - now always-on configuration.
    
    Returns:
        Dict with current always-on configuration status
    """
    return {
        'mode': 'always_on',
        'version': FEATURE_FLAGS_VERSION,
        'smart_nlp_routing': True,
        'smart_nlp_tone': True,
        'smart_corrections': True,
        'flags_removed': True,
        'allowlists_removed': True,
        'rollback_note': 'All features permanently enabled for production stability'
    }

def expense_repair_enabled() -> bool:
    """
    Feature flag for expense repair logic in /ai-chat endpoint
    Provides instant kill-switch capabilities for production safety
    """
    return os.getenv("EXPENSE_REPAIR_ENABLED", "true").lower() in {"1", "true", "yes", "on"}

def get_expense_repair_config() -> dict:
    """
    Get comprehensive configuration for expense repair system
    """
    return {
        "repair_enabled": expense_repair_enabled(),
        "circuit_breaker_enabled": os.getenv("EXPENSE_CIRCUIT_BREAKER", "true").lower() in {"1", "true", "yes", "on"},
        "repair_logging_enabled": os.getenv("EXPENSE_REPAIR_LOGGING", "true").lower() in {"1", "true", "yes", "on"}
    }

# ==============================
# WEB-ONLY NUDGING FEATURE FLAGS
# ==============================

# Master users who always get access to new features (for testing)
MASTER_USERS = set(os.getenv("MASTER_USERS", "chowdhurysujan71@gmail.com").split(","))

def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean value from environment variable."""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")

def _is_master_user(user_email: str | None = None) -> bool:
    """Check if user is a master user who gets early access."""
    if not user_email:
        try:
            from flask_login import current_user
            if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                user_email = getattr(current_user, 'email', None)
            else:
                user_email = None
        except Exception:
            user_email = None
    
    return user_email is not None and user_email in MASTER_USERS

def can_use_nudges(user_email: str | None = None) -> bool:
    """Check if user can access web-only nudging features."""
    # Master users always get access
    if _is_master_user(user_email):
        logger.debug(f"Master user {user_email} granted nudges access")
        return True
    
    # Check flag status (default OFF for safety)
    enabled = _get_env_bool("NUDGES_ENABLED", False)
    logger.debug(f"Nudges flag for user {user_email}: {enabled}")
    return enabled

def can_edit_in_chat(user_email: str | None = None) -> bool:
    """Check if user can use chat expense editing."""
    # Master users always get access
    if _is_master_user(user_email):
        return True
    
    return _get_env_bool("CHAT_EDIT_ENABLED", False)

def can_receive_spending_alerts(user_email: str | None = None) -> bool:
    """Check if user can receive spending spike alerts."""
    # Master users always get access
    if _is_master_user(user_email):
        return True
    
    return _get_env_bool("SPENDING_ALERTS_ENABLED", False)

def can_use_push_notifications(user_email: str | None = None) -> bool:
    """Check if user can use push notifications."""
    # Master users always get access  
    if _is_master_user(user_email):
        return True
    
    return _get_env_bool("PUSH_NOTIFICATIONS_ENABLED", False)

def get_nudging_features_status(user_email: str | None = None) -> dict:
    """Get status of all nudging features for a user."""
    return {
        "nudges_enabled": can_use_nudges(user_email),
        "chat_edit_enabled": can_edit_in_chat(user_email),
        "spending_alerts_enabled": can_receive_spending_alerts(user_email),
        "push_notifications_enabled": can_use_push_notifications(user_email),
        "is_master_user": _is_master_user(user_email),
        "master_users": len(MASTER_USERS)
    }

# Boot time initialization logging
logger.info(f"Feature flags initialized: version={FEATURE_FLAGS_VERSION} ALL_FEATURES=ON (no flags, no allowlists)")