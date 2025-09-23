"""
Feature Flags for FinBrain - Always On Configuration
All features are now enabled by default for production stability
"""

import os
import logging
from typing import Set, List, Optional

logger = logging.getLogger("finbrain.feature_flags")

# Import centralized config
from utils.config import FEATURE_FLAGS_VERSION

def is_smart_nlp_enabled(psid_hash: Optional[str] = None) -> bool:
    """
    SMART_NLP_ROUTING is now always enabled.
    Kept for backward compatibility during transition.
    
    Args:
        psid_hash: User's PSID hash (ignored, always returns True)
        
    Returns:
        Always True - feature is permanently enabled
    """
    return True

def is_smart_tone_enabled(psid_hash: Optional[str] = None) -> bool:
    """
    SMART_NLP_TONE is now always enabled.
    Kept for backward compatibility during transition.
    
    Args:
        psid_hash: User's PSID hash (ignored, always returns True)
        
    Returns:
        Always True - feature is permanently enabled
    """
    return True

def is_smart_corrections_enabled(psid_hash: Optional[str] = None) -> bool:
    """
    SMART_CORRECTIONS is now always enabled.
    Kept for backward compatibility during transition.
    
    Args:
        psid_hash: User's PSID hash (ignored, always returns True)
        
    Returns:
        Always True - feature is permanently enabled
    """
    return True

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

# Boot time initialization logging
logger.info(f"Feature flags initialized: version={FEATURE_FLAGS_VERSION} ALL_FEATURES=ON (no flags, no allowlists)")