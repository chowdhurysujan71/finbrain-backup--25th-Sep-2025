"""
Clean production router: AI-first with deterministic fallback
Single path decision making with comprehensive telemetry
"""
import time
import logging
from typing import Dict, Any

from flags import FLAGS
from config import AI_PROVIDER, AI_ENABLED, AI_TIMEOUT_MS
from ai_adapter import generate
from limiter import per_user_ok, global_ok, get_stats as get_limiter_stats
from deterministic import deterministic_reply

logger = logging.getLogger(__name__)

class ProductionRouter:
    """Clean router: prefer AI, fall back on failure/limits"""
    
    def __init__(self):
        self.stats = {
            "total_requests": 0,
            "ai_requests": 0,
            "fallback_requests": 0,
            "ai_errors": 0,
            "rate_limited": 0
        }
        logger.info("Production router initialized - AI-first with deterministic fallback")
    
    def route(self, message: str, user_id: str) -> Dict[str, Any]:
        """
        Route message: AI-first with comprehensive fallback
        Returns complete routing decision with metadata
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # Check rate limits first
        user_rate_ok = per_user_ok(user_id)
        global_rate_ok = global_ok()
        
        # Try AI if enabled and within limits
        if FLAGS.ai_enabled and AI_PROVIDER != "none" and user_rate_ok and global_rate_ok:
            ai_result = generate(f"User said: \"{message}\"\nIf it's an expense, return a short confirmation + category guess + tip if relevant.\nOtherwise, answer briefly.")
            
            if ai_result["ok"]:
                self.stats["ai_requests"] += 1
                logger.info(f"AI route success in {ai_result['latency_ms']}ms")
                
                return {
                    "path": "ai",
                    "text": ai_result["text"],
                    "latency_ms": ai_result["latency_ms"],
                    "routing_time_ms": int((time.time() - start_time) * 1000)
                }
            else:
                self.stats["ai_errors"] += 1
                logger.warning(f"AI failed: {ai_result.get('error', 'unknown')}")
                
                return {
                    "path": "fallback", 
                    "reason": "ai_error",
                    "ai_error": ai_result.get("error", "unknown"),
                    "text": deterministic_reply(message),
                    "routing_time_ms": int((time.time() - start_time) * 1000)
                }
        
        else:
            # Determine fallback reason
            if not FLAGS.ai_enabled:
                reason = "ai_disabled"
            elif AI_PROVIDER == "none":
                reason = "provider_none"
            elif not user_rate_ok:
                reason = "user_rate_limit"
                self.stats["rate_limited"] += 1
            elif not global_rate_ok:
                reason = "global_rate_limit"
                self.stats["rate_limited"] += 1
            else:
                reason = "unknown"
            
            self.stats["fallback_requests"] += 1
            
            return {
                "path": "fallback",
                "reason": reason,
                "text": deterministic_reply(message),
                "routing_time_ms": int((time.time() - start_time) * 1000)
            }
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Comprehensive telemetry - env vs runtime truth"""
        return {
            "config": {
                "ai_enabled_env_default": AI_ENABLED,
                "ai_enabled_effective": FLAGS.ai_enabled,
                "ai_provider": AI_PROVIDER,
                "ai_timeout_ms": AI_TIMEOUT_MS,
                "rl": {
                    "user_cap_per_min": 2,
                    "global_cap_per_min": 10
                }
            },
            "stats": self.stats.copy(),
            "rate_limiting": get_limiter_stats(),
            "timestamp": time.time()
        }

# Global router instance
router = ProductionRouter()