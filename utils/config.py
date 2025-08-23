"""
FinBrain Centralized Configuration
Single source of truth for all configuration to prevent drift
"""

import os
import logging

logger = logging.getLogger("utils.config")

# Configuration version for cache busting
FEATURE_FLAGS_VERSION = os.environ.get("FEATURE_FLAGS_VERSION", "always_on_v1")

# AI features are now always on (no flags)
AI_FEATURES_ENABLED = True
TONE_FEATURES_ENABLED = True
CORRECTIONS_FEATURES_ENABLED = True

def get_config_summary():
    """Get current configuration summary"""
    return {
        'version': FEATURE_FLAGS_VERSION,
        'ai_enabled': AI_FEATURES_ENABLED,
        'tone_enabled': TONE_FEATURES_ENABLED,
        'corrections_enabled': CORRECTIONS_FEATURES_ENABLED,
        'timestamp': '2025-08-23'
    }

def log_config_banner():
    """Log configuration banner on startup"""
    config = get_config_summary()
    logger.info(f"[CONFIG] version={config['version']} ai=on tone=on corrections=on")

# Initialize configuration logging
log_config_banner()