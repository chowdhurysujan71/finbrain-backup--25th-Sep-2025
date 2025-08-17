"""
Sliding Window Rate Limiter - Clean Implementation
Single source of truth for AI rate limiting with configurable limits
"""

import time
from collections import deque
from config import AI_RL_USER_LIMIT, AI_RL_WINDOW_SEC, AI_RL_GLOBAL_LIMIT


class SlidingWindowLimiter:
    """Sliding window rate limiter with precise timing"""
    
    def __init__(self, limit, window_sec):
        self.limit = limit
        self.window = window_sec
        self.store = {}  # {key: deque[timestamps]}

    def allow(self, key, now=None):
        """
        Check if request is allowed within rate limit
        
        Returns:
            (allowed: bool, retry_in_seconds: int)
        """
        now = now or time.time()
        q = self.store.setdefault(key, deque())
        
        # Remove expired timestamps
        while q and (now - q[0]) > self.window:
            q.popleft()
        
        # Check if under limit
        if len(q) < self.limit:
            q.append(now)
            return True, 0
        
        # Calculate retry time
        retry_in = self.window - (now - q[0])
        return False, int(max(1, retry_in))

    def get_remaining(self, key, now=None):
        """Get remaining requests in current window"""
        now = now or time.time()
        q = self.store.get(key, deque())
        
        # Remove expired timestamps
        while q and (now - q[0]) > self.window:
            q.popleft()
            
        return max(0, self.limit - len(q))


# Instantiate using config (no magic numbers)
RL2_USER = SlidingWindowLimiter(limit=AI_RL_USER_LIMIT, window_sec=AI_RL_WINDOW_SEC)
RL2_GLOBAL = SlidingWindowLimiter(limit=AI_RL_GLOBAL_LIMIT, window_sec=AI_RL_WINDOW_SEC)


def can_use_ai(psid):
    """
    Check if AI can be used for this user
    
    Returns:
        (allowed: bool, retry_in_seconds: int)
    """
    ok_user, retry_u = RL2_USER.allow(f"user:{psid}")
    ok_global, retry_g = RL2_GLOBAL.allow("global")
    
    if ok_user and ok_global:
        return True, 0
    
    return False, max(retry_u, retry_g)


def fallback_blurb(retry_in):
    """Generate fallback message with retry time"""
    return (
        f"Quick breather to keep things snappy. "
        f"I'll resume smart analysis in ~{retry_in}s. Want a quick action meanwhile?"
    )


def get_rate_limit_status(psid):
    """Get current rate limit status for user"""
    user_remaining = RL2_USER.get_remaining(f"user:{psid}")
    global_remaining = RL2_GLOBAL.get_remaining("global")
    
    return {
        'user_remaining': user_remaining,
        'user_limit': AI_RL_USER_LIMIT,
        'global_remaining': global_remaining,
        'global_limit': AI_RL_GLOBAL_LIMIT,
        'window_sec': AI_RL_WINDOW_SEC
    }