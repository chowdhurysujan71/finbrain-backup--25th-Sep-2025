"""
Advanced AI rate limiter with per-PSID sliding 60s windows + global per-minute caps
Supports Redis backend (optional) and comprehensive telemetry
"""
import os
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Configuration from environment
AI_ENABLED = os.environ.get("AI_ENABLED", "false").lower() == "true"
AI_MAX_CALLS_PER_MIN = int(os.environ.get("AI_MAX_CALLS_PER_MIN", "10"))
AI_MAX_CALLS_PER_MIN_PER_PSID = int(os.environ.get("AI_MAX_CALLS_PER_MIN_PER_PSID", "5"))

@dataclass
class RateLimitResult:
    """Rate limit check result"""
    ai_allowed: bool
    reason: str  # "ok" | "per_psid_limit" | "global_limit" | "ai_disabled"
    tokens_remaining: Optional[int]
    window_reset_at: str  # ISO8601
    psid_calls_in_window: int = 0
    global_calls_this_minute: int = 0

@dataclass
class RateLimitEvent:
    """Rate limit event for telemetry"""
    psid_hash: str
    reset_in_s: int
    reason: str
    at: str  # ISO8601

class AdvancedAILimiter:
    """
    Advanced AI rate limiter with sliding windows and global caps
    Supports both in-memory and Redis backends
    """
    
    def __init__(self, use_redis: bool = False):
        self.use_redis = use_redis
        self.redis_client = None
        
        # In-memory storage (fallback or primary)
        self.psid_windows: Dict[str, deque] = defaultdict(lambda: deque())
        self.global_minute_calls: Dict[str, int] = defaultdict(int)
        
        # Telemetry storage
        self.rate_limit_events: List[RateLimitEvent] = []
        self.stats = {
            'ai_calls_ok_minute': 0,
            'ai_calls_blocked_per_psid': 0,
            'ai_calls_blocked_global': 0,
            'rl2_errors_last_5m': 0
        }
        
        # Initialize Redis if requested
        if use_redis:
            self._init_redis()
        
        logger.info(f"Advanced AI Limiter initialized: redis={use_redis}, "
                   f"global_limit={AI_MAX_CALLS_PER_MIN}/min, "
                   f"per_psid_limit={AI_MAX_CALLS_PER_MIN_PER_PSID}/min")
    
    def _init_redis(self):
        """Initialize Redis client (optional upgrade)"""
        try:
            import redis
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()  # Test connection
            logger.info("Redis backend initialized for AI rate limiting")
        except Exception as e:
            logger.warning(f"Redis initialization failed, falling back to in-memory: {e}")
            self.use_redis = False
            self.redis_client = None
    
    def check_rate_limit(self, psid_hash: str) -> RateLimitResult:
        """
        Check if AI call is allowed for this PSID
        Returns comprehensive rate limit information
        """
        now = time.time()
        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        
        # Check if AI is globally disabled
        if not AI_ENABLED:
            return RateLimitResult(
                ai_allowed=False,
                reason="ai_disabled",
                tokens_remaining=None,
                window_reset_at=self._get_next_minute_iso(),
                psid_calls_in_window=0,
                global_calls_this_minute=0
            )
        
        # Check limits based on backend
        if self.use_redis and self.redis_client:
            return self._check_rate_limit_redis(psid_hash, now, current_minute)
        else:
            return self._check_rate_limit_memory(psid_hash, now, current_minute)
    
    def _check_rate_limit_memory(self, psid_hash: str, now: float, current_minute: str) -> RateLimitResult:
        """Check rate limits using in-memory storage"""
        # Clean old entries from sliding window (60 seconds)
        psid_window = self.psid_windows[psid_hash]
        while psid_window and psid_window[0] <= now - 60:
            psid_window.popleft()
        
        # Get current counts
        psid_calls = len(psid_window)
        global_calls = self.global_minute_calls[current_minute]
        
        # Check per-PSID limit first
        if psid_calls >= AI_MAX_CALLS_PER_MIN_PER_PSID:
            self._record_rate_limit_event(psid_hash, "per_psid_limit")
            self.stats['ai_calls_blocked_per_psid'] += 1
            
            return RateLimitResult(
                ai_allowed=False,
                reason="per_psid_limit",
                tokens_remaining=0,
                window_reset_at=self._get_next_minute_iso(),
                psid_calls_in_window=psid_calls,
                global_calls_this_minute=global_calls
            )
        
        # Check global limit
        if global_calls >= AI_MAX_CALLS_PER_MIN:
            self._record_rate_limit_event(psid_hash, "global_limit")
            self.stats['ai_calls_blocked_global'] += 1
            
            return RateLimitResult(
                ai_allowed=False,
                reason="global_limit",
                tokens_remaining=AI_MAX_CALLS_PER_MIN_PER_PSID - psid_calls,
                window_reset_at=self._get_next_minute_iso(),
                psid_calls_in_window=psid_calls,
                global_calls_this_minute=global_calls
            )
        
        # Allow the call and increment counters
        psid_window.append(now)
        self.global_minute_calls[current_minute] += 1
        self.stats['ai_calls_ok_minute'] += 1
        
        return RateLimitResult(
            ai_allowed=True,
            reason="ok",
            tokens_remaining=AI_MAX_CALLS_PER_MIN_PER_PSID - psid_calls - 1,
            window_reset_at=self._get_next_minute_iso(),
            psid_calls_in_window=psid_calls + 1,
            global_calls_this_minute=global_calls + 1
        )
    
    def _check_rate_limit_redis(self, psid_hash: str, now: float, current_minute: str) -> RateLimitResult:
        """Check rate limits using Redis backend"""
        try:
            # Redis keys
            psid_key = f"ai:psid:{psid_hash}:{current_minute}"
            global_key = f"ai:global:{current_minute}"
            
            # Get current counts
            psid_calls = int((self.redis_client.get(psid_key) if self.redis_client else None) or 0)
            global_calls = int((self.redis_client.get(global_key) if self.redis_client else None) or 0)
            
            # Check per-PSID limit
            if psid_calls >= AI_MAX_CALLS_PER_MIN_PER_PSID:
                self._record_rate_limit_event(psid_hash, "per_psid_limit")
                self.stats['ai_calls_blocked_per_psid'] += 1
                
                return RateLimitResult(
                    ai_allowed=False,
                    reason="per_psid_limit",
                    tokens_remaining=0,
                    window_reset_at=self._get_next_minute_iso(),
                    psid_calls_in_window=psid_calls,
                    global_calls_this_minute=global_calls
                )
            
            # Check global limit
            if global_calls >= AI_MAX_CALLS_PER_MIN:
                self._record_rate_limit_event(psid_hash, "global_limit")
                self.stats['ai_calls_blocked_global'] += 1
                
                return RateLimitResult(
                    ai_allowed=False,
                    reason="global_limit",
                    tokens_remaining=AI_MAX_CALLS_PER_MIN_PER_PSID - psid_calls,
                    window_reset_at=self._get_next_minute_iso(),
                    psid_calls_in_window=psid_calls,
                    global_calls_this_minute=global_calls
                )
            
            # Increment counters atomically
            if self.redis_client:
                pipe = self.redis_client.pipeline()
                pipe.incr(psid_key)
                pipe.expire(psid_key, 120)  # 2 minute expiry for safety
                pipe.incr(global_key)
                pipe.expire(global_key, 120)
                pipe.execute()
            
            self.stats['ai_calls_ok_minute'] += 1
            
            return RateLimitResult(
                ai_allowed=True,
                reason="ok",
                tokens_remaining=AI_MAX_CALLS_PER_MIN_PER_PSID - psid_calls - 1,
                window_reset_at=self._get_next_minute_iso(),
                psid_calls_in_window=psid_calls + 1,
                global_calls_this_minute=global_calls + 1
            )
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fall back to in-memory
            return self._check_rate_limit_memory(psid_hash, now, current_minute)
    
    def _record_rate_limit_event(self, psid_hash: str, reason: str):
        """Record rate limit event for telemetry"""
        now = datetime.now(timezone.utc)
        reset_time = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        reset_in_s = int((reset_time - now).total_seconds())
        
        event = RateLimitEvent(
            psid_hash=psid_hash,
            reset_in_s=reset_in_s,
            reason=reason,
            at=now.isoformat()
        )
        
        # Keep only last 100 events for memory efficiency
        self.rate_limit_events.append(event)
        if len(self.rate_limit_events) > 100:
            self.rate_limit_events.pop(0)
    
    def _get_next_minute_iso(self) -> str:
        """Get next minute boundary as ISO8601 string"""
        now = datetime.now(timezone.utc)
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        return next_minute.isoformat()
    
    def record_rl2_error(self):
        """Record RL-2 error for telemetry"""
        self.stats['rl2_errors_last_5m'] += 1
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get comprehensive telemetry data for /ops endpoint"""
        # Clean old minute buckets
        current_minute = datetime.now().strftime("%Y%m%d%H%M")
        old_minutes = [k for k in self.global_minute_calls.keys() if k < current_minute]
        for old_minute in old_minutes:
            del self.global_minute_calls[old_minute]
        
        # Clean old rate limit events (keep last 5 minutes)
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.rate_limit_events = [
            event for event in self.rate_limit_events
            if datetime.fromisoformat(event.at.replace('Z', '+00:00')) > cutoff_time
        ]
        
        return {
            'ai_calls_ok_minute': self.stats['ai_calls_ok_minute'],
            'ai_calls_blocked_per_psid': self.stats['ai_calls_blocked_per_psid'],
            'ai_calls_blocked_global': self.stats['ai_calls_blocked_global'],
            'ai_rate_limited_events': [
                {
                    'psid_hash': event.psid_hash[:8] + "...",  # Truncate for privacy
                    'reset_in_s': event.reset_in_s,
                    'reason': event.reason,
                    'at': event.at
                }
                for event in self.rate_limit_events[-10:]  # Last 10 events
            ],
            'rl2_errors_last_5m': self.stats['rl2_errors_last_5m'],
            'config': {
                'AI_ENABLED': AI_ENABLED,
                'AI_MAX_CALLS_PER_MIN': AI_MAX_CALLS_PER_MIN,
                'AI_MAX_CALLS_PER_MIN_PER_PSID': AI_MAX_CALLS_PER_MIN_PER_PSID,
                'use_redis': self.use_redis
            }
        }
    
    def reset_stats(self):
        """Reset statistics (useful for testing)"""
        self.stats = {
            'ai_calls_ok_minute': 0,
            'ai_calls_blocked_per_psid': 0,
            'ai_calls_blocked_global': 0,
            'rl2_errors_last_5m': 0
        }
        self.rate_limit_events.clear()

# Global instance
advanced_ai_limiter = AdvancedAILimiter()