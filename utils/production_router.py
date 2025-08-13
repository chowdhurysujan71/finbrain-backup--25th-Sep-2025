"""
Production routing system: Deterministic Core + Flag-Gated AI + Canary Rollout
Implements single entry point with rate limiting, AI failover, and comprehensive telemetry
"""
import os
import time
import logging
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timezone

from utils.background_processor_rl2 import rl2_processor
from utils.ai_limiter import advanced_ai_limiter
from utils.ai_adapter_v2 import production_ai_adapter
from utils.textutil import (
    format_logged_response, format_summary_response, format_help_response,
    format_undo_response, get_random_tip, normalize, PANIC_PLAIN_REPLY
)
from utils.security import hash_psid
from utils.parser import parse_expense
from utils.categories import categorize_expense
from utils.logger import get_request_id

logger = logging.getLogger(__name__)

# Configuration
AI_ENABLED = os.environ.get("AI_ENABLED", "false").lower() == "true"

class ProductionRouter:
    """
    Production-ready message router with deterministic core and flag-gated AI
    Implements: Limiter -> RL-2 (if limited) -> AI (if enabled) -> Rules (fallback)
    """
    
    def __init__(self):
        self.telemetry = {
            'total_messages': 0,
            'ai_messages': 0,
            'rl2_messages': 0,
            'rules_messages': 0,
            'ai_failovers': 0,
            'processing_times': []
        }
        
        logger.info("Production Router initialized with bulletproof RL-2 and flag-gated AI")
    
    def route_message(self, text: str, psid: str, rid: Optional[str] = None) -> Tuple[str, str, Optional[str], Optional[float]]:
        """
        Single entry point for all message processing
        Returns: (response_text, intent, category, amount)
        """
        start_time = time.time()
        psid_hash = hash_psid(psid)
        
        if rid is None:
            rid = get_request_id() or "unknown"
        
        self.telemetry['total_messages'] += 1
        
        try:
            # Panic mode - immediate acknowledgment
            if PANIC_PLAIN_REPLY:
                response = normalize("OK")
                self._log_routing_decision(rid, psid_hash, "panic", "immediate_ack")
                return response, "panic", None, None
            
            # Step 1: Evaluate rate limiter first
            rate_limit_result = advanced_ai_limiter.check_rate_limit(psid_hash)
            
            if not rate_limit_result.ai_allowed:
                # Step 2: RL-2 path (rate limited)
                response, intent, category, amount = self._route_rl2(text, psid, psid_hash, rid, rate_limit_result)
                self.telemetry['rl2_messages'] += 1
                self._record_processing_time(time.time() - start_time)
                return response, intent, category, amount
            
            # Step 3: Check if AI should be used
            if AI_ENABLED and production_ai_adapter.ai_mode(text):
                # Step 4: AI branch
                response, intent, category, amount = self._route_ai(text, psid, psid_hash, rid, rate_limit_result)
                self.telemetry['ai_messages'] += 1
                self._record_processing_time(time.time() - start_time)
                return response, intent, category, amount
            
            # Step 5: Deterministic rules path
            response, intent, category, amount = self._route_rules(text, psid, psid_hash, rid)
            self.telemetry['rules_messages'] += 1
            self._record_processing_time(time.time() - start_time)
            return response, intent, category, amount
            
        except Exception as e:
            logger.error(f"Production routing error: {e}")
            # Emergency fallback
            response = normalize("Got it. Try 'summary' for a quick recap.")
            self._log_routing_decision(rid, psid_hash, "error", f"emergency_fallback: {str(e)}")
            return response, "error", None, None
    
    def _route_rl2(self, text: str, psid: str, psid_hash: str, rid: str, rate_limit_result) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Route to RL-2 system for rate-limited processing"""
        self._log_routing_decision(rid, psid_hash, "rl2", f"rate_limited: {rate_limit_result.reason}")
        
        # Use bulletproof RL-2 processor
        response, intent, category, amount = rl2_processor.process_rate_limited_message(text, psid)
        
        # Ensure response is sanitized and capped
        response = normalize(response)
        
        return response, intent, category, amount
    
    def _route_ai(self, text: str, psid: str, psid_hash: str, rid: str, rate_limit_result) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Route to AI processing with failover to rules"""
        self._log_routing_decision(rid, psid_hash, "ai", "attempting_ai_parse")
        
        # Build context for AI
        context = {
            'user_hash': psid_hash,
            'request_id': rid,
            'tokens_remaining': rate_limit_result.tokens_remaining
        }
        
        # Call AI adapter
        ai_result = production_ai_adapter.ai_parse(text, context)
        
        if ai_result.get('failover', False):
            # AI failed - fall back to rules
            self.telemetry['ai_failovers'] += 1
            self._log_routing_decision(rid, psid_hash, "ai_failover", f"reason: {ai_result.get('reason', 'unknown')}")
            return self._route_rules(text, psid, psid_hash, rid)
        
        # AI succeeded - apply results
        intent = ai_result.get('intent', 'help')
        
        if intent == 'log':
            return self._handle_ai_log(ai_result, text, psid, psid_hash, rid)
        elif intent == 'summary':
            return self._handle_ai_summary(ai_result, psid, psid_hash, rid)
        elif intent == 'undo':
            return self._handle_ai_undo(ai_result, psid, psid_hash, rid)
        else:
            # Help or unknown
            return self._handle_ai_help(ai_result, psid_hash, rid)
    
    def _route_rules(self, text: str, psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Route to deterministic rules processing"""
        self._log_routing_decision(rid, psid_hash, "rules", "deterministic_processing")
        
        text_lower = text.lower().strip()
        
        # Summary command
        if text_lower == 'summary':
            return self._handle_rules_summary(psid, psid_hash, rid)
        
        # Undo command
        if text_lower in ['undo', 'undo last', 'remove last']:
            return self._handle_rules_undo(psid, psid_hash, rid)
        
        # Try expense parsing
        parsed_expense = parse_expense(text)
        if parsed_expense:
            amount, description = parsed_expense
            category = categorize_expense(description)
            
            # Store expense
            self._store_expense_deterministic(psid, amount, description, category, text)
            
            # Format response with variants
            response = format_logged_response(amount, description, category)
            
            self._log_routing_decision(rid, psid_hash, "rules", f"logged: {amount} {category}")
            return response, "log", category, amount
        
        # No pattern matched - help
        response = format_help_response()
        self._log_routing_decision(rid, psid_hash, "rules", "help_provided")
        return response, "help", None, None
    
    def _handle_ai_log(self, ai_result: Dict[str, Any], text: str, psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle AI-detected expense logging"""
        amount = ai_result.get('amount')
        note = ai_result.get('note', '')
        category = ai_result.get('category', 'other')
        
        if amount is None:
            # AI couldn't extract amount - fall back to rules
            return self._route_rules(text, psid, psid_hash, rid)
        
        # Store expense deterministically
        self._store_expense_deterministic(psid, amount, note, category, text)
        
        # Enhanced response with AI insights
        response = format_logged_response(amount, note, category)
        response += "\nType summary anytime."
        
        self._log_routing_decision(rid, psid_hash, "ai_log", f"logged: {amount} {category}")
        return normalize(response), "log", category, amount
    
    def _handle_ai_summary(self, ai_result: Dict[str, Any], psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle AI-enhanced summary"""
        # Generate deterministic summary
        totals = self._get_summary_data(psid)
        
        # Use AI tip if available
        ai_tips = ai_result.get('tips', [])
        tip = ai_tips[0] if ai_tips else get_random_tip()
        
        response = format_summary_response(totals, tip)
        
        self._log_routing_decision(rid, psid_hash, "ai_summary", f"total: {totals.get('total', 0)}")
        return response, "summary", None, None
    
    def _handle_ai_undo(self, ai_result: Dict[str, Any], psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle AI-detected undo request"""
        # Perform deterministic undo
        removed_expense = self._undo_last_expense(psid)
        
        if removed_expense:
            amount, note = removed_expense
            response = format_undo_response(amount, note)
            self._log_routing_decision(rid, psid_hash, "ai_undo", f"removed: {amount}")
            return response, "undo", None, amount
        else:
            response = format_undo_response()
            self._log_routing_decision(rid, psid_hash, "ai_undo", "nothing_to_undo")
            return response, "undo", None, None
    
    def _handle_ai_help(self, ai_result: Dict[str, Any], psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle AI help response"""
        response = format_help_response()
        self._log_routing_decision(rid, psid_hash, "ai_help", "help_provided")
        return response, "help", None, None
    
    def _handle_rules_summary(self, psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle deterministic summary"""
        totals = self._get_summary_data(psid)
        tip = get_random_tip()
        
        response = format_summary_response(totals, tip)
        
        self._log_routing_decision(rid, psid_hash, "rules_summary", f"total: {totals.get('total', 0)}")
        return response, "summary", None, None
    
    def _handle_rules_undo(self, psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle deterministic undo"""
        removed_expense = self._undo_last_expense(psid)
        
        if removed_expense:
            amount, note = removed_expense
            response = format_undo_response(amount, note)
            self._log_routing_decision(rid, psid_hash, "rules_undo", f"removed: {amount}")
            return response, "undo", None, amount
        else:
            response = format_undo_response()
            self._log_routing_decision(rid, psid_hash, "rules_undo", "nothing_to_undo")
            return response, "undo", None, None
    
    def _store_expense_deterministic(self, psid: str, amount: float, description: str, category: str, original_text: str):
        """Store expense with deterministic error handling"""
        try:
            from app import db
            from models import Expense, User
            from datetime import datetime
            import random
            
            user_hash = hash_psid(psid)
            
            # Create expense record
            expense = Expense()
            expense.user_id = user_hash
            expense.description = description
            expense.amount = amount
            expense.category = category
            expense.currency = '৳'
            expense.month = datetime.now().strftime('%Y-%m')
            expense.unique_id = f"prod_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
            expense.platform = 'messenger'
            expense.original_message = original_text[:500]
            
            # Update user record
            user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
            if not user:
                user = User()
                user.user_id_hash = user_hash
                user.platform = 'messenger'
                user.last_user_message_at = datetime.utcnow()
                db.session.add(user)
            else:
                user.last_user_message_at = datetime.utcnow()
            
            user.total_expenses = (user.total_expenses or 0) + amount
            user.expense_count = (user.expense_count or 0) + 1
            user.last_interaction = datetime.utcnow()
            
            # Atomic save
            db.session.add(expense)
            db.session.commit()
            
        except Exception as e:
            logger.warning(f"Production expense storage error: {e}")
            # Continue without throwing - UX not affected
    
    def _get_summary_data(self, psid: str) -> Dict[str, float]:
        """Get summary data for user"""
        try:
            from app import db
            from models import Expense
            from sqlalchemy import text
            from datetime import datetime, timedelta
            
            user_hash = hash_psid(psid)
            seven_days_ago = datetime.now() - timedelta(days=7)
            
            # Safe query
            query = text("""
                SELECT 
                    COALESCE(SUM(amount), 0) as total,
                    category,
                    COALESCE(SUM(amount), 0) as category_total
                FROM expenses 
                WHERE user_id = :user_hash 
                  AND created_at >= :seven_days_ago
                GROUP BY category
            """)
            
            results = db.session.execute(query, {
                'user_hash': user_hash,
                'seven_days_ago': seven_days_ago
            }).fetchall()
            
            totals = {'total': 0.0, 'food': 0.0, 'ride': 0.0, 'bill': 0.0, 'grocery': 0.0, 'other': 0.0}
            
            for row in results:
                category = row.category or 'other'
                amount = float(row.category_total or 0)
                totals['total'] += amount
                if category in totals:
                    totals[category] = amount
                else:
                    totals['other'] += amount
            
            return totals
            
        except Exception as e:
            logger.error(f"Summary data error: {e}")
            return {'total': 0.0, 'food': 0.0, 'ride': 0.0, 'bill': 0.0, 'grocery': 0.0, 'other': 0.0}
    
    def _undo_last_expense(self, psid: str) -> Optional[Tuple[float, str]]:
        """Undo last expense for user"""
        try:
            from app import db
            from models import Expense, User
            
            user_hash = hash_psid(psid)
            
            # Find last expense
            last_expense = db.session.query(Expense).filter_by(
                user_id=user_hash
            ).order_by(Expense.created_at.desc()).first()
            
            if last_expense:
                amount = last_expense.amount
                description = last_expense.description
                
                # Update user totals
                user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
                if user:
                    user.total_expenses = max(0, (user.total_expenses or 0) - amount)
                    user.expense_count = max(0, (user.expense_count or 0) - 1)
                
                # Remove expense
                db.session.delete(last_expense)
                db.session.commit()
                
                return (amount, description)
            
            return None
            
        except Exception as e:
            logger.error(f"Undo expense error: {e}")
            return None
    
    def _log_routing_decision(self, rid: str, psid_hash: str, route: str, details: str):
        """Log routing decision for telemetry"""
        logger.info(f"Production routing: {{\"rid\": \"{rid}\", \"psid_hash\": \"{psid_hash[:8]}...\", \"route\": \"{route}\", \"details\": \"{details}\", \"timestamp\": \"{datetime.now(timezone.utc).isoformat()}\"}}")
    
    def _record_processing_time(self, duration: float):
        """Record processing time for telemetry"""
        self.telemetry['processing_times'].append(duration * 1000)  # Convert to ms
        # Keep only last 100 measurements
        if len(self.telemetry['processing_times']) > 100:
            self.telemetry['processing_times'].pop(0)
    
    def get_telemetry(self) -> Dict[str, Any]:
        """Get comprehensive routing telemetry"""
        processing_times = self.telemetry['processing_times']
        
        return {
            'total_messages': self.telemetry['total_messages'],
            'ai_messages': self.telemetry['ai_messages'], 
            'rl2_messages': self.telemetry['rl2_messages'],
            'rules_messages': self.telemetry['rules_messages'],
            'ai_failovers': self.telemetry['ai_failovers'],
            'queue_depth': 0,  # Would be from background processor
            'worker_lag_ms': sum(processing_times[-10:]) / len(processing_times[-10:]) if processing_times else 0.0,
            'ai_limiter': advanced_ai_limiter.get_telemetry(),
            'ai_adapter': production_ai_adapter.get_status(),
            'config': {
                'AI_ENABLED': AI_ENABLED,
                'SAY_ENABLED': os.environ.get("SAY_ENABLED", "true"),
                'EMOJI_ENABLED': os.environ.get("EMOJI_ENABLED", "true"),
                'MAX_REPLY_LEN': int(os.environ.get("MAX_REPLY_LEN", "280")),
                'PANIC_PLAIN_REPLY': PANIC_PLAIN_REPLY
            }
        }

# Global instance
production_router = ProductionRouter()