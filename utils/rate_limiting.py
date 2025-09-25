"""
Rate limiting utility for FinBrain application
Provides centralized limiter configuration for both app and PWA components
"""
import os
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)

def get_rate_limit_storage():
    """Get rate limiting storage backend with Redis fallback"""
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        logger.warning("No REDIS_URL available, using in-memory rate limiting storage")
        return None
    
    # Fix environment variable format issues
    if redis_url.startswith('REDIS_URL='):
        redis_url = redis_url.split('=', 1)[1]
    if redis_url.startswith('"') and redis_url.endswith('"'):
        redis_url = redis_url[1:-1]
    
    try:
        import redis
        from flask_limiter.util import get_remote_address
        
        # Create Redis connection with timeout
        redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        redis_client.ping()  # Test connection
        
        logger.info("Rate limiting configured with Redis storage")
        return f"redis://{redis_url.split('@')[-1]}"  # Return cleaned URL for Flask-Limiter
        
    except Exception as e:
        logger.warning(f"Redis not available for rate limiting, falling back to in-memory: {e}")
        return None

# Create limiter instance with Redis storage or in-memory fallback
storage_uri = get_rate_limit_storage()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120 per minute"],
    storage_uri=storage_uri
)