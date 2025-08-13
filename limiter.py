"""
Simplified rate limiter for AI requests
Per-user and global rate limiting with clear boolean checks
"""
import time
from collections import defaultdict, deque
from config import AI_MAX_CALLS_PER_MIN, AI_MAX_CALLS_PER_MIN_PER_PSID

# In-memory rate limiting (simple sliding window)
user_requests = defaultdict(deque)
global_requests = deque()

def per_user_ok(user_id: str) -> bool:
    """Check if user is within rate limit (2/min)"""
    now = time.time()
    user_queue = user_requests[user_id]
    
    # Remove old requests (older than 60 seconds)
    while user_queue and user_queue[0] < now - 60:
        user_queue.popleft()
    
    # Check if under limit
    if len(user_queue) < AI_MAX_CALLS_PER_MIN_PER_PSID:
        user_queue.append(now)
        return True
    
    return False

def global_ok() -> bool:
    """Check if global rate limit is OK (10/min)"""
    now = time.time()
    
    # Remove old requests
    while global_requests and global_requests[0] < now - 60:
        global_requests.popleft()
    
    # Check if under limit
    if len(global_requests) < AI_MAX_CALLS_PER_MIN:
        global_requests.append(now)
        return True
    
    return False

def get_stats():
    """Get current rate limiting stats"""
    now = time.time()
    
    # Clean old requests for accurate counts
    while global_requests and global_requests[0] < now - 60:
        global_requests.popleft()
    
    active_users = 0
    for user_id, queue in user_requests.items():
        while queue and queue[0] < now - 60:
            queue.popleft()
        if queue:
            active_users += 1
    
    return {
        "global_requests_last_min": len(global_requests),
        "global_limit": AI_MAX_CALLS_PER_MIN,
        "active_users_last_min": active_users,
        "per_user_limit": AI_MAX_CALLS_PER_MIN_PER_PSID
    }