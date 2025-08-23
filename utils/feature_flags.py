"""
Feature Flags and Canary System for FinBrain
Provides safe rollout of SMART_NLP_ROUTING and SMART_CORRECTIONS with instant rollback capability
"""

import os
import logging
from typing import Set, List, Optional

logger = logging.getLogger("finbrain.feature_flags")

# Feature flag environment variables
SMART_NLP_ROUTING_DEFAULT = os.environ.get("SMART_NLP_ROUTING_DEFAULT", "false").lower() == "true"
SMART_NLP_TONE_FOR_STD = os.environ.get("SMART_NLP_TONE_FOR_STD", "false").lower() == "true"
SMART_CORRECTIONS_DEFAULT = os.environ.get("SMART_CORRECTIONS_DEFAULT", "false").lower() == "true"

# Allowlist for canary rollout - comma-separated PSID hashes
FEATURE_ALLOWLIST_SMART_NLP = set(
    hash_val.strip() 
    for hash_val in os.environ.get("FEATURE_ALLOWLIST_SMART_NLP_ROUTING", "").split(",") 
    if hash_val.strip()
)

FEATURE_ALLOWLIST_SMART_NLP_TONE = set(
    hash_val.strip() 
    for hash_val in os.environ.get("FEATURE_ALLOWLIST_SMART_NLP_TONE_FOR_STD", "").split(",") 
    if hash_val.strip()
)

FEATURE_ALLOWLIST_SMART_CORRECTIONS = set(
    hash_val.strip() 
    for hash_val in os.environ.get("FEATURE_ALLOWLIST_SMART_CORRECTIONS", "").split(",") 
    if hash_val.strip()
)

def is_smart_nlp_enabled(psid_hash: Optional[str] = None) -> bool:
    """
    Check if SMART_NLP_ROUTING is enabled for this user.
    
    Args:
        psid_hash: User's PSID hash for allowlist check
        
    Returns:
        True if feature is enabled for this user, False otherwise
    """
    # Global flag check first
    if not SMART_NLP_ROUTING_DEFAULT:
        # Even if global flag is off, check allowlist for canary users
        if psid_hash and psid_hash in FEATURE_ALLOWLIST_SMART_NLP:
            logger.info(f"SMART_NLP enabled for canary user: {psid_hash[:8]}...")
            return True
        return False
    
    # Global flag is on, check if user is explicitly excluded
    # (Future enhancement: could add exclusion list)
    return True

def is_smart_tone_enabled(psid_hash: Optional[str] = None) -> bool:
    """
    Check if SMART_NLP_TONE_FOR_STD is enabled for this user.
    Allows coach-tone replies in STD mode when enabled.
    
    Args:
        psid_hash: User's PSID hash for allowlist check
        
    Returns:
        True if coach tone is enabled for STD mode, False otherwise
    """
    if not SMART_NLP_TONE_FOR_STD:
        # Check allowlist for canary users
        if psid_hash and psid_hash in FEATURE_ALLOWLIST_SMART_NLP_TONE:
            logger.info(f"SMART_NLP_TONE enabled for canary user: {psid_hash[:8]}...")
            return True
        return False
    
    return True

def is_smart_corrections_enabled(psid_hash: Optional[str] = None) -> bool:
    """
    Check if SMART_CORRECTIONS is enabled for this user.
    
    Args:
        psid_hash: User's PSID hash for allowlist check
        
    Returns:
        True if corrections are enabled for this user, False otherwise
    """
    # Global flag check first
    if not SMART_CORRECTIONS_DEFAULT:
        # Even if global flag is off, check allowlist for canary users
        if psid_hash and psid_hash in FEATURE_ALLOWLIST_SMART_CORRECTIONS:
            logger.info(f"SMART_CORRECTIONS enabled for canary user: {psid_hash[:8]}...")
            return True
        return False
    
    # Global flag is on, check if user is explicitly excluded
    # (Future enhancement: could add exclusion list)
    return True

def feature_enabled(psid_hash: str, feature_name: str) -> bool:
    """
    Generic feature flag checker for any feature.
    
    Args:
        psid_hash: User's PSID hash
        feature_name: Name of the feature to check
        
    Returns:
        True if feature is enabled for this user, False otherwise
    """
    if feature_name == "SMART_CORRECTIONS":
        return is_smart_corrections_enabled(psid_hash)
    elif feature_name == "SMART_NLP_ROUTING":
        return is_smart_nlp_enabled(psid_hash)
    elif feature_name == "SMART_NLP_TONE":
        return is_smart_tone_enabled(psid_hash)
    else:
        logger.warning(f"Unknown feature flag: {feature_name}")
        return False

def get_canary_status():
    """
    Get current status of all feature flags and canary deployments.
    
    Returns:
        Dict with flag states, allowlist sizes, and rollback instructions
    """
    return {
        'smart_nlp_routing_default': SMART_NLP_ROUTING_DEFAULT,
        'smart_nlp_tone_for_std': SMART_NLP_TONE_FOR_STD,
        'smart_corrections_default': SMART_CORRECTIONS_DEFAULT,
        'allowlist_sizes': {
            'smart_nlp': len(FEATURE_ALLOWLIST_SMART_NLP),
            'smart_nlp_tone': len(FEATURE_ALLOWLIST_SMART_NLP_TONE),
            'smart_corrections': len(FEATURE_ALLOWLIST_SMART_CORRECTIONS)
        },
        'allowlist_previews': {
            'smart_nlp': list(FEATURE_ALLOWLIST_SMART_NLP)[:3],
            'smart_nlp_tone': list(FEATURE_ALLOWLIST_SMART_NLP_TONE)[:3],
            'smart_corrections': list(FEATURE_ALLOWLIST_SMART_CORRECTIONS)[:3]
        },
        'rollback_instructions': {
            'instant_disable': 'Set SMART_NLP_ROUTING_DEFAULT=false and SMART_NLP_TONE_FOR_STD=false',
            'canary_only': 'Clear SMART_NLP_ROUTING_DEFAULT, use FEATURE_ALLOWLIST_SMART_NLP only'
        }
    }

# Boot time initialization logging
logger.info(f"Feature flags initialized: SMART_NLP_ROUTING={SMART_NLP_ROUTING_DEFAULT}, "
           f"SMART_NLP_TONE={SMART_NLP_TONE_FOR_STD}, "
           f"canary_users=NLP:{len(FEATURE_ALLOWLIST_SMART_NLP)},TONE:{len(FEATURE_ALLOWLIST_SMART_NLP_TONE)},CORR:{len(FEATURE_ALLOWLIST_SMART_CORRECTIONS)}")