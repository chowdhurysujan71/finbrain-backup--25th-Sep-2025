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

# Boot time initialization logging
logger.info(f"Feature flags initialized: version={FEATURE_FLAGS_VERSION} ALL_FEATURES=ON (no flags, no allowlists)")