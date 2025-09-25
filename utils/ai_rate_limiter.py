"""
AI Rate Limiter with sliding 60s window per-PSID and global limits
Phase 1 implementation - deterministic, never blocks request threads
"""
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class RateLimitResult:
    """Result of AI rate limit check"""
    ai_allowed: bool
    reason: str  # "ok", "per_psid_limit", "global_limit"
    tokens_remaining: int | None
    window_reset_at: str  # ISO8601

class AIRateLimiter:
    """Sliding window AI rate limiter with per-PSID and global limits"""
    
    def __init__(self):
        # Configuration from centralized config
        from config import AI_RL_GLOBAL_LIMIT, AI_RL_USER_LIMIT
        self.ai_enabled = os.getenv("AI_ENABLED", "false").lower() == "true"
        self.max_calls_per_min = AI_RL_GLOBAL_LIMIT  
        self.max_calls_per_min_per_psid = AI_RL_USER_LIMIT
        
        # Sliding window storage: psid -> List[timestamp]
        self.psid_windows: dict[str, list[float]] = {}
        
        # Global sliding window
        self.global_window: list[float] = []
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Window duration (60 seconds)
        self.window_seconds = 60.0
        
        logger.info(f"AI Rate Limiter initialized: max_global={self.max_calls_per_min}/min, max_per_psid={self.max_calls_per_min_per_psid}/min")
    
    def check_rate_limit(self, psid_hash: str) -> RateLimitResult:
        """
        Check if AI call is allowed for given PSID hash
        Uses sliding 60-second window
        Thread-safe, never blocks
        """
        current_time = time.time()
        
        with self._lock:
            # Clean expired entries
            self._cleanup_expired_entries(current_time)
            
            # Check per-PSID limit
            if psid_hash not in self.psid_windows:
                self.psid_windows[psid_hash] = []
            
            psid_calls = len(self.psid_windows[psid_hash])
            global_calls = len(self.global_window)
            
            # Calculate tokens remaining and window reset
            psid_tokens_remaining = max(0, self.max_calls_per_min_per_psid - psid_calls)
            global_tokens_remaining = max(0, self.max_calls_per_min - global_calls)
            
            # Window reset time (next full minute)
            reset_time = current_time + self.window_seconds
            reset_iso = datetime.fromtimestamp(reset_time, tz=UTC).isoformat()
            
            # Check limits
            if psid_calls >= self.max_calls_per_min_per_psid:
                return RateLimitResult(
                    ai_allowed=False,
                    reason="per_psid_limit",
                    tokens_remaining=0,
                    window_reset_at=reset_iso
                )
            
            if global_calls >= self.max_calls_per_min:
                return RateLimitResult(
                    ai_allowed=False,
                    reason="global_limit", 
                    tokens_remaining=0,
                    window_reset_at=reset_iso
                )
            
            # All checks passed
            return RateLimitResult(
                ai_allowed=True,
                reason="ok",
                tokens_remaining=min(psid_tokens_remaining, global_tokens_remaining),
                window_reset_at=reset_iso
            )
    
    def record_ai_call(self, psid_hash: str) -> None:
        """
        Record an AI call for rate limiting
        Should be called AFTER a successful AI call
        """
        current_time = time.time()
        
        with self._lock:
            # Add to per-PSID window
            if psid_hash not in self.psid_windows:
                self.psid_windows[psid_hash] = []
            self.psid_windows[psid_hash].append(current_time)
            
            # Add to global window
            self.global_window.append(current_time)
            
            # Clean up old entries
            self._cleanup_expired_entries(current_time)
    
    def _cleanup_expired_entries(self, current_time: float) -> None:
        """Remove entries older than window_seconds"""
        cutoff_time = current_time - self.window_seconds
        
        # Clean global window
        self.global_window = [t for t in self.global_window if t > cutoff_time]
        
        # Clean per-PSID windows
        for psid_hash in list(self.psid_windows.keys()):
            self.psid_windows[psid_hash] = [t for t in self.psid_windows[psid_hash] if t > cutoff_time]
            
            # Remove empty PSID entries to save memory
            if not self.psid_windows[psid_hash]:
                del self.psid_windows[psid_hash]
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics"""
        current_time = time.time()
        
        with self._lock:
            self._cleanup_expired_entries(current_time)
            
            return {
                "ai_enabled": self.ai_enabled,
                "max_calls_per_min": self.max_calls_per_min,
                "max_calls_per_min_per_psid": self.max_calls_per_min_per_psid,
                "current_global_calls": len(self.global_window),
                "active_psids": len(self.psid_windows),
                "window_seconds": self.window_seconds
            }
    
    def reset_all(self):
        """Reset all rate limiting windows for testing"""
        with self._lock:
            self.psid_windows.clear()
            self.global_window.clear()
        logger.info("AI rate limiter reset: all windows cleared")

# Global rate limiter instance
ai_rate_limiter = AIRateLimiter()