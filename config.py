"""
Streamlined configuration for FinBrain
Single source of truth for all runtime flags and environment variables
"""
import os

def env_bool(k, d=False): 
    return str(os.getenv(k, str(d))).strip().lower() in ("1","true","t","yes","y","on")

def env_int(k, d): 
    try: 
        return int(os.getenv(k, str(d)))
    except: 
        return d

# Core AI Configuration
AI_ENABLED = env_bool("AI_ENABLED", False)
AI_PROVIDER = os.getenv("AI_PROVIDER", "none")
AI_TIMEOUT_MS = env_int("AI_TIMEOUT_MS", 3000)

# Application Constants - Single Source of Truth
MSG_MAX_CHARS = env_int("MSG_MAX_CHARS", 280)              # message length guardrail
TIMEZONE = os.getenv("TIMEZONE", "Asia/Dhaka")             # default timezone
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "৳")        # default currency symbol
DEFAULT_CATEGORY = os.getenv("DEFAULT_CATEGORY", "other")  # fallback expense category

# AI Rate Limiting - Single Source of Truth
AI_RL_USER_LIMIT = env_int("AI_RL_USER_LIMIT", 4)          # per-user replies in window
AI_RL_WINDOW_SEC = env_int("AI_RL_WINDOW_SEC", 60)         # window duration in seconds  
AI_RL_GLOBAL_LIMIT = env_int("AI_RL_GLOBAL_LIMIT", 120)    # global budget

# Legacy rate limiting (deprecated - use AI_RL_* above)
AI_MAX_CALLS_PER_MIN = env_int("AI_MAX_CALLS_PER_MIN", AI_RL_GLOBAL_LIMIT)
AI_MAX_CALLS_PER_MIN_PER_PSID = env_int("AI_MAX_CALLS_PER_MIN_PER_PSID", AI_RL_USER_LIMIT)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Facebook Integration
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")

# Admin Auth
ADMIN_USER = os.getenv("ADMIN_USER", "")
ADMIN_PASS = os.getenv("ADMIN_PASS", "")

# Security
SESSION_SECRET = os.getenv("SESSION_SECRET", "")

# AI Provider Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Rate Limiting (RPM = Requests Per Minute) - Legacy, use AI_RL_* instead
AI_MAX_RPM_GLOBAL = AI_RL_GLOBAL_LIMIT
AI_MAX_RPM_USER = AI_RL_USER_LIMIT