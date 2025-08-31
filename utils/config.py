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

# PCA (Precision Capture & Audit) Configuration
PCA_ENABLED = True  # PCA system is available

# Coaching configuration
COACH_MAX_TURNS = int(os.getenv('COACH_MAX_TURNS', '3'))
COACH_SESSION_TTL_SEC = int(os.getenv('COACH_SESSION_TTL_SEC', '300'))  # 5 min
COACH_COOLDOWN_SEC = int(os.getenv('COACH_COOLDOWN_SEC', '900'))  # 15 min
COACH_PER_DAY_MAX = int(os.getenv('COACH_PER_DAY_MAX', '6'))

# Application Constants
MSG_MAX_CHARS = int(os.getenv('MSG_MAX_CHARS', '280'))  
TIMEZONE = os.getenv('TIMEZONE', 'Asia/Dhaka')
CURRENCY_SYMBOL = os.getenv('CURRENCY_SYMBOL', '৳')

# AI Rate Limiting Configuration
AI_RL_USER_LIMIT = int(os.getenv('AI_RL_USER_LIMIT', '4'))
AI_RL_WINDOW_SEC = int(os.getenv('AI_RL_WINDOW_SEC', '60'))  
AI_RL_GLOBAL_LIMIT = int(os.getenv('AI_RL_GLOBAL_LIMIT', '120'))

def get_config_summary():
    """Get current configuration summary"""
    # Import here to avoid circular imports
    try:
        from utils.pca_flags import pca_flags
        pca_status = pca_flags.get_status()
    except Exception:
        pca_status = {'mode': 'UNAVAILABLE', 'error': 'import_failed'}
    
    return {
        'version': FEATURE_FLAGS_VERSION,
        'ai_enabled': AI_FEATURES_ENABLED,
        'tone_enabled': TONE_FEATURES_ENABLED,
        'corrections_enabled': CORRECTIONS_FEATURES_ENABLED,
        'pca_enabled': PCA_ENABLED,
        'pca_status': pca_status,
        'timestamp': '2025-08-26'
    }

def log_config_banner():
    """Log configuration banner on startup"""
    config = get_config_summary()
    pca_mode = config.get('pca_status', {}).get('mode', 'UNAVAILABLE')
    logger.info(f"[CONFIG] version={config['version']} ai=on tone=on corrections=on pca={pca_mode.lower()}")

# Initialize configuration logging
log_config_banner()