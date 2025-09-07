"""
Rate limiter for job enqueue operations
"""
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_time: float
    reason: Optional[str] = None

class JobRateLimiter:
    """Rate limiter for job enqueue operations per user"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.default_limit = 60  # jobs per hour
        self.window_seconds = 3600  # 1 hour
        
        # In-memory fallback if Redis not available
        self.memory_store = {}
        
        logger.info(f"Job rate limiter initialized: {self.default_limit} jobs per hour")
    
    def check_rate_limit(self, user_id: str, limit: Optional[int] = None) -> RateLimitResult:
        """
        Check if user is within rate limit for job enqueue
        
        Args:
            user_id: User identifier
            limit: Custom limit (default: 60/hour)
            
        Returns:
            RateLimitResult with allow status and details
        """
        effective_limit = limit or self.default_limit
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        try:
            if self.redis_client:
                return self._check_redis_rate_limit(user_id, effective_limit, current_time, window_start)
            else:
                return self._check_memory_rate_limit(user_id, effective_limit, current_time, window_start)
        except Exception as e:
            logger.error(f"Rate limit check failed for user {user_id}: {e}")
            # Fail open - allow request if rate limiter is broken
            return RateLimitResult(
                allowed=True,
                remaining=effective_limit,
                reset_time=current_time + self.window_seconds,
                reason="rate_limiter_error"
            )
    
    def _check_redis_rate_limit(self, user_id: str, limit: int, current_time: float, 
                               window_start: float) -> RateLimitResult:
        """Check rate limit using Redis"""
        key = f"rate_limit:jobs:{user_id}"
        
        # Use Redis sorted set for sliding window
        pipe = self.redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current entries
        pipe.zcard(key)
        
        # Add current request
        pipe.zadd(key, {str(current_time): current_time})
        
        # Set expiration
        pipe.expire(key, self.window_seconds)
        
        results = pipe.execute()
        current_count = results[1]  # Count after cleanup
        
        remaining = max(0, limit - current_count - 1)  # -1 for current request
        reset_time = current_time + self.window_seconds
        
        if current_count >= limit:
            # Remove the request we just added since it's not allowed
            self.redis_client.zrem(key, str(current_time))
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                reason=f"Rate limit exceeded: {current_count}/{limit} requests in window"
            )
        
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=reset_time
        )
    
    def _check_memory_rate_limit(self, user_id: str, limit: int, current_time: float,
                                window_start: float) -> RateLimitResult:
        """Check rate limit using in-memory store (fallback)"""
        if user_id not in self.memory_store:
            self.memory_store[user_id] = []
        
        # Clean old entries
        self.memory_store[user_id] = [t for t in self.memory_store[user_id] if t > window_start]
        
        current_count = len(self.memory_store[user_id])
        
        if current_count >= limit:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=current_time + self.window_seconds,
                reason=f"Rate limit exceeded: {current_count}/{limit} requests in window"
            )
        
        # Add current request
        self.memory_store[user_id].append(current_time)
        
        remaining = limit - current_count - 1
        
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=current_time + self.window_seconds
        )
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get rate limit stats for user"""
        current_time = time.time()
        window_start = current_time - self.window_seconds
        
        try:
            if self.redis_client:
                key = f"rate_limit:jobs:{user_id}"
                # Clean and count
                self.redis_client.zremrangebyscore(key, 0, window_start)
                current_count = self.redis_client.zcard(key)
            else:
                if user_id not in self.memory_store:
                    current_count = 0
                else:
                    # Clean old entries
                    self.memory_store[user_id] = [t for t in self.memory_store[user_id] if t > window_start]
                    current_count = len(self.memory_store[user_id])
            
            return {
                "user_id": user_id,
                "current_count": current_count,
                "limit": self.default_limit,
                "remaining": max(0, self.default_limit - current_count),
                "window_seconds": self.window_seconds,
                "reset_time": current_time + self.window_seconds
            }
            
        except Exception as e:
            logger.error(f"Failed to get rate limit stats for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "current_count": 0,
                "limit": self.default_limit,
                "remaining": self.default_limit,
                "window_seconds": self.window_seconds,
                "reset_time": current_time + self.window_seconds,
                "error": str(e)
            }

# Global rate limiter instance (will be initialized with Redis client)
job_rate_limiter = None

def get_job_rate_limiter(redis_client=None):
    """Get or create job rate limiter instance"""
    global job_rate_limiter
    if job_rate_limiter is None:
        job_rate_limiter = JobRateLimiter(redis_client)
    return job_rate_limiter