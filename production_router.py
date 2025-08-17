"""
Clean production router: AI-first with deterministic fallback
Single path decision making with comprehensive telemetry
"""
import time
import logging
from typing import Dict, Any

from flags import FLAGS
from config import AI_PROVIDER, AI_ENABLED, AI_TIMEOUT_MS, GEMINI_MODEL
from limiter import per_user_ok, global_ok, get_stats as get_limiter_stats
from deterministic import deterministic_reply

# Dynamic provider import
llm_generate = None
if AI_PROVIDER.strip() == "gemini":
    try:
        from ai_adapter_gemini import generate as llm_generate, get_stats as get_ai_stats
    except ImportError:
        llm_generate = None
        get_ai_stats = lambda: {"error": "Gemini adapter not available"}
elif AI_PROVIDER.strip() == "openai":
    try:
        from ai_adapter_openai import generate as llm_generate, get_stats as get_ai_stats
    except ImportError:
        llm_generate = None
        get_ai_stats = lambda: {"error": "OpenAI adapter not available"}
else:
    get_ai_stats = lambda: {"provider": "none", "configured": False}

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
        if FLAGS.ai_enabled and llm_generate is not None and user_rate_ok and global_rate_ok:
            ai_result = llm_generate(f"User said: \"{message}\"\nIf it's an expense, return a short confirmation + category guess + tip if relevant.\nOtherwise, answer briefly.")
            
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
            elif llm_generate is None:
                reason = "provider_unavailable"
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
        from config import AI_RL_USER_LIMIT, AI_RL_WINDOW_SEC, AI_RL_GLOBAL_LIMIT
        config = {
            "ai_enabled_env_default": AI_ENABLED,
            "ai_enabled_effective": FLAGS.ai_enabled,
            "ai_provider": AI_PROVIDER,
            "ai_timeout_ms": AI_TIMEOUT_MS,
            "rl": {
                "user_cap_per_window": AI_RL_USER_LIMIT,
                "global_cap_per_window": AI_RL_GLOBAL_LIMIT,
                "window_sec": AI_RL_WINDOW_SEC
            }
        }
        
        # Add provider-specific config
        if AI_PROVIDER == "gemini":
            config["gemini_model"] = GEMINI_MODEL
        
        return {
            "config": config,
            "ai_adapter": get_ai_stats(),
            "stats": self.stats.copy(),
            "rate_limiting": get_limiter_stats(),
            "timestamp": time.time()
        }

# Global router instance
router = ProductionRouter()