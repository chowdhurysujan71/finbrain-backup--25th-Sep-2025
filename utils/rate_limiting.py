"""
Rate limiting utility for FinBrain application
Provides centralized limiter configuration for both app and PWA components
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Create limiter instance with default configuration
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"]
)