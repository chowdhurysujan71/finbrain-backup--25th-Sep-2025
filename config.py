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

# Rate Limiting
AI_MAX_CALLS_PER_MIN = env_int("AI_MAX_CALLS_PER_MIN", 10)
AI_MAX_CALLS_PER_MIN_PER_PSID = env_int("AI_MAX_CALLS_PER_MIN_PER_PSID", 2)

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

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")