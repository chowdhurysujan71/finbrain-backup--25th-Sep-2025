"""
Clean production router: AI-first with deterministic fallback
Single path decision making with comprehensive telemetry
Enhanced with context packet system integration
"""
import time
import logging
from typing import Dict, Any

from flags import FLAGS
from config import AI_PROVIDER, AI_ENABLED, AI_TIMEOUT_MS, GEMINI_MODEL
from limiter import can_use_ai, fallback_blurb
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
        
        def get_limiter_stats():
            return {
                "user_limit": AI_RL_USER_LIMIT,
                "global_limit": AI_RL_GLOBAL_LIMIT,
                "window_sec": AI_RL_WINDOW_SEC
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
    
    def route_message(self, text: str, psid: str, rid: str) -> tuple:
        """
        Route message using optimized context-driven AI reply
        
        Args:
            text: User message
            psid: Facebook Page-Scoped ID
            rid: Request ID
            
        Returns:
            (response_text, intent, category, amount)
        """
        try:
            from limiter import can_use_ai, fallback_blurb
            
            # Check rate limiting
            allowed, retry_in = can_use_ai(psid)
            if not allowed:
                response_text = fallback_blurb(retry_in)
                return (response_text, "rate_limited", None, None)
            
            # Use inline optimized AI reply to avoid circular imports
            insight = self._ai_reply_with_context(psid, text)
            
            # Format response with 280-char limit
            msg = f"{insight['summary']}\n{insight['action']}\n{insight['question']}"
            if len(msg) > 280:
                msg = msg[:260] + "… Want details?"
            
            # Extract intent and amount if possible (for compatibility)
            intent = "ai_context_driven"
            category = None
            amount = None
            
            # Try to extract amount from summary for logging
            import re
            amount_match = re.search(r'৳([\d,]+)', insight['summary'])
            if amount_match:
                try:
                    amount = float(amount_match.group(1).replace(',', ''))
                except:
                    amount = None
            
            return (msg, intent, category, amount)
            
        except Exception as e:
            logger.error(f"Context-driven routing failed: {e}")
            # Fallback to deterministic reply
            fallback_text = deterministic_reply(text)
            return (fallback_text, "fallback_error", None, None)
    
    def _ai_reply_with_context(self, psid: str, user_text: str) -> dict:
        """
        Internal optimized AI reply with context packet and schema enforcement
        """
        import json
        
        SYSTEM_PROMPT = """
        You are a personable financial coach.
        Use ONLY the provided user_context for numeric advice.
        If user_context is empty or too thin (<2 categories), do not generalize.
        Instead, ask for one high-leverage step to collect data (e.g., "log 3 biggest spends today" or "import last month").
        Reply in 2–3 sentences max. Give one next step and one question. Avoid jargon. Use numbers when helpful.
        """
        
        try:
            # 1. Build context from DB (inline to avoid circular import)
            ctx = self._build_context_inline(psid)
            
            # 2. If context too thin → don't allow generic advice
            if ctx["total_spend_30d"] == 0 or len(ctx["top_cats"]) < 2:
                return {
                    "summary": "I don't see enough recent spend to personalize this.",
                    "action":  "Log your 3 biggest expenses today so I can analyze.",
                    "question": "Want to log them now or import last month's data?"
                }

            # 3. Call AI with enforced schema
            from ai_adapter_gemini import generate_with_schema
            
            response_format = {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "action": {"type": "string"},
                    "question": {"type": "string"}
                },
                "required": ["summary", "action", "question"]
            }
            
            full_prompt = f"Question: {user_text}\n\nuser_context={json.dumps(ctx, ensure_ascii=False)}"
            
            result = generate_with_schema(
                user_text=full_prompt,
                system_prompt=SYSTEM_PROMPT,
                response_schema=response_format
            )
            
            if result["ok"] and "data" in result:
                return result["data"]
            
            # AI failed - return structured fallback using context
            top_cat = ctx["top_cats"][0] if ctx["top_cats"] else None
            if top_cat:
                category = top_cat["category"]
                amount = top_cat["amount"]
                delta = top_cat["delta_pct"]
                return {
                    "summary": f"{category.title()} is ৳{amount:,} in 30d, {delta:+d}% vs prior.",
                    "action": f"Consider setting a {category} budget cap.",
                    "question": f"Want to see your {category} breakdown or set a limit?"
                }
            else:
                return {
                    "summary": f"Total spend is ৳{ctx['total_spend_30d']:,} in 30 days.",
                    "action": "Track spending by category for better insights.",
                    "question": "Want to log recent expenses or see trends?"
                }
                
        except Exception as e:
            logger.error(f"AI reply failed for {psid[:8]}...: {e}")
            # 4. Guarantee structured dict even on error
            return {
                "summary": "Here's a quick take.",
                "action": "Want me to set a simple cap for you?",
                "question": "See details or set a goal?"
            }
    
    def _build_context_inline(self, psid: str) -> dict:
        """
        Inline context building to avoid circular imports
        """
        try:
            from app import db
            from models import Expense
            from utils.security import hash_psid
            from datetime import datetime, timedelta
            
            user_hash = hash_psid(psid)
            now = datetime.utcnow()
            
            # Get 30-day spending by category
            start_30d = now - timedelta(days=30)
            expenses_30d = db.session.query(Expense).filter(
                Expense.user_id == user_hash,
                Expense.created_at >= start_30d
            ).all()
            
            # Get previous 30-day spending for comparison
            start_60d = now - timedelta(days=60)
            start_prev30 = now - timedelta(days=31)
            expenses_prev30 = db.session.query(Expense).filter(
                Expense.user_id == user_hash,
                Expense.created_at >= start_60d,
                Expense.created_at <= start_prev30
            ).all()
            
            # Group by category
            current_cats = {}
            for expense in expenses_30d:
                category = expense.category or 'other'
                current_cats[category] = current_cats.get(category, 0) + expense.amount
            
            prev_cats = {}
            for expense in expenses_prev30:
                category = expense.category or 'other'
                prev_cats[category] = prev_cats.get(category, 0) + expense.amount
            
            # Calculate deltas and top categories
            top_cats = []
            for category, amount in current_cats.items():
                prev_amount = prev_cats.get(category, 0)
                if prev_amount > 0:
                    delta_pct = int(round(100 * (amount - prev_amount) / prev_amount))
                else:
                    delta_pct = 100 if amount > 0 else 0
                
                top_cats.append({
                    "category": category,
                    "amount": int(amount),
                    "delta_pct": delta_pct
                })
            
            # Sort by amount, top 5
            top_cats = sorted(top_cats, key=lambda x: x["amount"], reverse=True)[:5]
            
            return {
                "income_30d": 0,  # Placeholder - could be enhanced
                "top_cats": top_cats,
                "total_spend_30d": int(sum(current_cats.values())),
                "recurring": [],  # Placeholder - could be enhanced
                "goals": [],      # Placeholder - could be enhanced
                "context_quality": "rich" if len(top_cats) >= 2 and sum(current_cats.values()) > 0 else "thin"
            }
            
        except Exception as e:
            logger.error(f"Context building failed: {e}")
            return {
                "income_30d": 0,
                "top_cats": [],
                "total_spend_30d": 0,
                "recurring": [],
                "goals": [],
                "context_quality": "thin"
            }

# Global router instance
router = ProductionRouter()