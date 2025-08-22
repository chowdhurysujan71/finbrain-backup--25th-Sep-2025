"""
Production routing system: Deterministic Core + Flag-Gated AI + Canary Rollout
Implements single entry point with rate limiting, AI failover, and comprehensive telemetry
"""

import os
import re
import time
import logging
import pathlib
import hashlib
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

# Money detection and unified parsing
from finbrain.router import contains_money
from parsers.expense import parse_amount_currency_category

# Single source of truth for user ID resolution  
from utils.identity import psid_hash
from utils.background_processor_rl2 import rl2_processor
from utils.ai_limiter import advanced_ai_limiter
from utils.ai_adapter_v2 import production_ai_adapter
from utils.textutil import (
    format_logged_response, format_summary_response, format_help_response,
    format_undo_response, get_random_tip, normalize, PANIC_PLAIN_REPLY
)
from utils.parser import parse_expense
from utils.categories import categorize_expense
from utils.logger import get_request_id

# Import performance monitoring
try:
    from finbrain.ops import perf
except ImportError:
    perf = None

# Flask imports for webhook blueprint
from flask import Blueprint, request, jsonify

# Log which router file each process loads with SHA verification
_P = pathlib.Path(__file__).resolve()
logging.warning("PRODUCTION_ROUTER_INIT file=%s sha=%s",
                _P, hashlib.sha256(_P.read_bytes()).hexdigest()[:12])

logger = logging.getLogger("finbrain.router")

# Performance tracking import
try:
    from finbrain.ops import perf
except ImportError:
    perf = None

# AI-path verification logger
ai_logger = logging.getLogger("finbrain.router")

# Configuration
AI_ENABLED = os.environ.get("AI_ENABLED", "false").lower() == "true"

# Summary detection patterns
SUMMARY_RE = re.compile(
    r"\b(summary|recap|overview|report|what did i spend|how much did i spend|show (me )?my (spend|spending|expenses))\b",
    re.IGNORECASE,
)

def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def _is_summary_command(text: str) -> bool:
    if not text:
        return False
    return bool(SUMMARY_RE.search(text)) or _norm_text(text) in {"summary", "recap", "report", "overview"}

def handle_summary(psid: str, text: str):
    """Deterministic summary handler that bypasses AI rate limits"""
    # Choose timeframe (fallback: last 7 days)
    end = datetime.utcnow()
    start = end - timedelta(days=7)
    
    # Get user summary data
    try:
        from services.summaries import build_user_summary, format_summary_text
        rollup = build_user_summary(psid, start, end)
        if not rollup:
            return "No recent spending found in the last 7 days."

        # Optional AI phrasing ONLY if enabled (but summary must not be blocked if AI is off/limited)
        if AI_ENABLED:
            try:
                from utils.ai_adapter_v2 import production_ai_adapter

                ai_result = production_ai_adapter.phrase_summary(rollup)
                if ai_result and not ai_result.get('failover', False):
                    return ai_result.get('text', format_summary_text(rollup))
            except Exception:
                pass
        
        return format_summary_text(rollup)
    except Exception as e:
        logger.error(f"Summary handler error: {e}")
        return "Unable to generate summary at this time."

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
    
    def _is_expense_message(self, text: str) -> bool:
        """Check if message looks like an expense (has numbers + keywords)"""
        import re
        
        # Look for numbers and expense-related keywords
        has_number = bool(re.search(r'\d+', text))
        expense_keywords = ['spent', 'paid', 'bought', 'cost', 'price', 'coffee', 'lunch', 'dinner', 'food', 'gas', 'fuel', 'uber', 'taxi']
        has_expense_keyword = any(keyword in text.lower() for keyword in expense_keywords)
        
        return bool(has_number and (has_expense_keyword or len(text.split()) <= 3))
    
    def route_message(self, text: str, psid: str, rid: str = "") -> Tuple[str, str, Optional[str], Optional[float]]:
        """
        Single entry point for all message processing
        Returns: (response_text, intent, category, amount)
        """
        start_time = time.time()
        user_hash = psid_hash(psid)
        
        if not rid:
            rid = get_request_id() or "unknown"
        
        self.telemetry['total_messages'] += 1
        
        try:
            # Panic mode - immediate acknowledgment
            if PANIC_PLAIN_REPLY:
                response = normalize("OK")
                self._log_routing_decision(rid, user_hash, "panic", "immediate_ack")
                return response, "panic", None, None
            
            # Step 1: MONEY DETECTION - Prioritizes LOG over SUMMARY
            # This must run before any SUMMARY logic to ensure new users can log expenses
            if contains_money(text):
                logger.info(f"[ROUTER] Money detected - forcing LOG intent: psid={psid[:8]}... text='{text[:50]}...'")
                
                # Parse using unified parser
                parsed_data = parse_amount_currency_category(text)
                if parsed_data and parsed_data.get('amount'):
                    # Route to unified LOG handler with idempotency protection
                    response, intent, category, amount = self._handle_unified_log(text, psid, user_hash, rid, parsed_data)
                    self._emit_structured_telemetry(rid, user_hash, "LOG", "money_detected", {
                        'amount': float(parsed_data['amount']),
                        'currency': parsed_data['currency'],
                        'category': parsed_data['category']
                    })
                    self._record_processing_time(time.time() - start_time)
                    return response, intent, category, amount
            
            # Step 2: Use intent router for command detection (only if no money detected)
            from utils.intent_router import detect_intent
            from utils.dispatcher import handle_message_dispatch
            
            intent = detect_intent(text)
            
            # Step 3: Route non-AI intents immediately (bypass rate limits)
            if intent in ["DIAGNOSTIC", "SUMMARY", "INSIGHT", "UNDO"]:
                # Only allow SUMMARY if no money was detected
                if intent == "SUMMARY" and contains_money(text):
                    logger.info(f"[ROUTER] Blocking SUMMARY due to money detection: psid={psid[:8]}...")
                    # Force to LOG path instead
                    parsed_data = parse_amount_currency_category(text)
                    if parsed_data and parsed_data.get('amount'):
                        response, intent, category, amount = self._handle_unified_log(text, psid, user_hash, rid, parsed_data)
                        self._emit_structured_telemetry(rid, user_hash, "LOG", "summary_blocked_by_money", {
                            'amount': float(parsed_data['amount']),
                            'currency': parsed_data['currency'], 
                            'category': parsed_data['category']
                        })
                        return response, intent, category, amount
                
                logger.info(f"[ROUTER] Deterministic intent={intent} psid={psid}")
                response_text, _ = handle_message_dispatch(user_hash, text)
                self._emit_structured_telemetry(rid, user_hash, intent, "deterministic_bypass", {})
                self._log_routing_decision(rid, user_hash, intent.lower(), "deterministic_bypass")
                return normalize(response_text), intent.lower(), None, None
            
            # Step 4: Handle expense logging with new parser
            if intent == "LOG_EXPENSE":
                from handlers.logger import handle_log
                result = handle_log(user_hash, text)
                response = result.get('text', 'Unable to log expense')
                self._emit_structured_telemetry(rid, user_hash, "LOG", "intent_log_expense", {})
                self._log_routing_decision(rid, user_hash, "log", "expense_logged")
                self._record_processing_time(time.time() - start_time)
                return normalize(response), "log", None, None
            
            # Step 4: Evaluate rate limiter for AI paths only
            rate_limit_result = advanced_ai_limiter.check_rate_limit(user_hash)

            if not rate_limit_result.ai_allowed:
                # Step 5: RL-2 path (rate limited)
                response, intent, category, amount = self._route_rl2(text, psid, user_hash, rid, rate_limit_result)
                self.telemetry['rl2_messages'] += 1
                self._record_processing_time(time.time() - start_time)
                return response, intent, category, amount
            
            # Step 6: Check if AI should be used (for expense messages)
            if AI_ENABLED and self._is_expense_message(text):
                # Step 7: AI branch with crash protection
                response, intent, category, amount = self._route_ai(text, psid, user_hash, rid, rate_limit_result)
                self.telemetry['ai_messages'] += 1
                self._record_processing_time(time.time() - start_time)
                return response, intent, category, amount
            
            # Step 8: Unknown intent - provide help
            response = (
                "I can help you track expenses! Try:\n"
                "• 'spent 100 on lunch' - to log an expense\n"
                "• 'summary' - to see your spending\n"
                "• 'insight' - for optimization tips"
            )
            self._log_routing_decision(rid, user_hash, "help", "unknown_intent")
            self._record_processing_time(time.time() - start_time)
            return normalize(response), "help", None, None
            
        except Exception as e:
            logger.error(f"Production routing error: {e}")
            # Emergency fallback - NO tip on unknown text
            response = normalize("I didn't understand that. Please try again.")
            self._log_routing_decision(rid, user_hash, "error", f"emergency_fallback: {str(e)}")
            return response, "error", None, None
    
    def _handle_expense_log(self, parsed_expense, text: str, psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle deterministic expense logging"""
        amount, description = parsed_expense
        category = categorize_expense(description)
        
        # Store expense deterministically
        self._store_expense_deterministic(psid, amount, description, category, text)
        
        # Generate response
        response = format_logged_response(amount, description, category)
        
        self._log_routing_decision(rid, psid_hash, "log", f"logged: {amount} {category}")
        return response, "log", category, amount
    
    def _route_rl2(self, text: str, psid: str, psid_hash: str, rid: str, rate_limit_result) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Route to RL-2 system for rate-limited processing"""
        self._log_routing_decision(rid, psid_hash, "rl2", f"rate_limited: {rate_limit_result.reason}")
        
        # Use bulletproof RL-2 processor
        response, intent, category, amount = rl2_processor.process_rate_limited_message(text, psid)
        
        # Ensure response is sanitized and capped
        response = normalize(response)
        
        return response, intent, category, amount
    
    def _route_ai(self, text: str, psid: str, psid_hash: str, rid: str, rate_limit_result) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Route to AI processing with defensive normalization - fixes 'function has no len()' crash"""
        self._log_routing_decision(rid, psid_hash, "ai", "attempting_ai_parse")
        
        try:
            # Try AI parsing with defensive normalization  
            from ai.expense_parse import parse_expense
            expense = parse_expense(text)
            
            # Save expense to database
            from utils.db import save_expense
            save_expense(
                user_identifier=psid_hash,
                description=f"{expense['category']} expense",
                amount=expense["amount"],
                category=expense["category"],
                platform="facebook",
                original_message=text,
                unique_id=rid
            )
            
            reply = f"✅ Logged: ৳{expense['amount']:.0f} for {expense['category'].lower()}"
            mode = "AI"
            
        except Exception:
            logger.exception("AI expense logging error")
            
            # Deterministic fallback: try regex parser
            from ai.expense_parse import regex_parse
            expense = regex_parse(text)  # very strict "spent {amt} on {cat}"
            if expense:
                try:
                    from utils.db import save_expense
                    save_expense(
                        user_identifier=psid_hash,
                        description=f"{expense['category']} expense",
                        amount=expense["amount"], 
                        category=expense["category"],
                        platform="facebook",
                        original_message=text,
                        unique_id=rid
                    )
                    reply = f"✅ Logged: ৳{expense['amount']:.0f} for {expense['category'].lower()}"
                    mode = "STD"
                except Exception as save_error:
                    logger.error(f"Regex save failed: {save_error}")
                    reply = "Something went wrong. Please try again."
                    mode = "ERR"
            else:
                reply = "I couldn't read that. Try: 'spent 200 on groceries' or 'coffee 50'"
                mode = "STD"
        
        # Add debug stamp  
        debug_stamp = f" | psid_hash={psid_hash[:8]}... | mode={mode}"
        response = normalize(reply + debug_stamp)
        
        self._log_routing_decision(rid, psid_hash, "ai_expense", f"logged_with_mode_{mode}")
        return response, "ai_expense_logged", expense.get('category') if 'expense' in locals() else None, expense.get('amount') if 'expense' in locals() else None
    
    def _route_rules(self, text: str, psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Route to deterministic rules processing"""
        self._log_routing_decision(rid, psid_hash, "rules", "deterministic_processing")
        
        text_lower = text.lower().strip()
        
        # Summary command (redundant check, but kept for compatibility)
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
        
        # Generate AI-powered response with intelligent tips
        response = self._generate_ai_logged_response(amount, note, category, ai_result.get('tips', []))
        
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
        """Handle AI help response with intelligent advice"""
        # Use AI-generated tips for advice/help requests
        ai_tips = ai_result.get('tips', [])
        note = ai_result.get('note', '')
        
        if ai_tips and ai_tips[0]:
            # Generate intelligent advice response (allow full length)
            response = ai_tips[0]
        elif note:
            # Fallback to rephrasing the question
            response = f"Good question about {note.lower()}. I'd suggest tracking expenses first to see patterns."
        else:
            # Last resort template
            response = format_help_response()
        
        self._log_routing_decision(rid, psid_hash, "ai_help", "help_provided")
        return normalize(response), "help", None, None
        
    def route_message_engagement(self, text: str, psid: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Engagement-driven message routing with UAT testing and personalization (deprecated)"""
        from utils.uat_system import uat_system
        from app import db
        
        # Start performance tracking
        start_time = time.time()
        
        # Check if we already have a hash (64 chars) or need to hash a PSID
        if psid and len(psid) == 64:  # Already hashed
            user_hash = psid
        else:
            from utils.identity import psid_hash
            user_hash = psid_hash(psid or "unknown")
        
        # AI-path verification logging: log entry
        ai_logger.info(f"ai_path_enter psid_hash={user_hash[:8]}... mid={rid} text_len={len(text)}")
        
        try:
            # Check for UAT commands first
            uat_response = self._handle_uat_commands(text, psid, rid)
            if uat_response:
                return uat_response
            
            # Handle active UAT testing
            if uat_system.is_uat_mode(psid):
                return self._handle_uat_flow(text, psid, rid)
            
            # Skip AI rate limiting for expense logging (only gate actual AI calls)
            # We'll check rate limits only when we need AI processing
            
            # Get user data and handle onboarding with fresh data
            # Use the already computed hash (user_hash is already defined above)
            
            # Simple user existence check - using correct field name
            from models import User
            user_exists = db.session.query(User.user_id_hash).filter_by(user_id_hash=user_hash).first()
            
            if not user_exists:
                # New user - handle onboarding
                user_data = {'is_new': True, 'has_completed_onboarding': False}
                return self._handle_onboarding(text, psid, user_data, rid)
            
            # For existing users, use simple intent-based routing
            from utils.intent_router import detect_intent
            intent = detect_intent(text)
            
            # DIAGNOSTIC COMMAND (temporary testing)
            if text.strip().lower() == "diag":
                return f"diag | type={type(user_hash).__name__} | psid_hash={user_hash[:8]}... | mode=STD", "diagnostic", None, None
            
            if intent == "SUMMARY":
                # Log non-AI path
                ai_logger.info(f"ai_path_exit psid_hash={user_hash[:8]}... mid={rid} intents=['summary'] mode=STD")
                from handlers.summary import handle_summary
                result = handle_summary(user_hash)
                return result.get('text', 'No spending data available'), 'summary', None, None
            
            elif intent == "INSIGHT":
                # Log non-AI path
                ai_logger.info(f"ai_path_exit psid_hash={user_hash[:8]}... mid={rid} intents=['insight'] mode=STD")
                from handlers.insight import handle_insight
                result = handle_insight(user_hash)
                return result.get('text', 'Unable to generate insights'), 'insight', None, None
            
            # Check if this is an expense logging message first
            from utils.parser import extract_expenses
            expense_list = extract_expenses(text)
            
            if expense_list and len(expense_list) > 0:
                # Convert to expected format for expense logging
                expense_parse_result = {
                    'expenses': expense_list,
                    'total_amount': sum(exp['amount'] for exp in expense_list),
                    'item_count': len(expense_list),
                    'original_text': text,
                    'success': True
                }
                # Log expense logging path
                ai_logger.info(f"ai_path_exit psid_hash={user_hash[:8]}... mid={rid} intents=['log_expense'] mode=LOG")
                # Handle expense logging with multiple items
                return self._handle_ai_expense_logging(expense_parse_result, psid, user_hash, rid)
            
            # Use conversational AI for non-expense messages
            from utils.conversational_ai import conversational_ai
            
            # AI-path logging: entering AI processing
            ai_logger.info(f"ai_path_enter psid_hash={user_hash[:8]}... mid={rid} intents=['conversational'] mode=AI")
            
            # Handle conversational queries with user-level memory
            # Pass the already-computed hash directly to avoid double-hashing
            response, intent_type = conversational_ai.handle_conversational_query_with_hash(user_hash, text)
            
            # AI-path logging: exiting AI processing
            ai_logger.info(f"ai_path_exit psid_hash={user_hash[:8]}... mid={rid} intents=['{intent_type}'] mode=AI")
            
            # Skip habit-forming elements for now (user_data not defined in this path)
                
            # Return conversational response
            return self._format_response(response), f"ai_{intent_type}", None, None
                
        except Exception as e:
            logger.error(f"Engagement routing error: {e}", exc_info=True)
            # Try simple command handlers with proper intent detection
            from utils.intent_router import detect_intent
            intent = detect_intent(text)
            
            if intent == "SUMMARY":
                try:
                    from handlers.summary import handle_summary
                    result = handle_summary(user_hash)
                    return result.get('text', 'Unable to generate summary'), 'summary', None, None
                except Exception as summary_error:
                    logger.error(f"Summary handler fallback error: {summary_error}")
                    return "📊 Summary temporarily unavailable. Your expenses are still being tracked!", 'summary', None, None
            
            # Final fallback with performance logging
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # Convert to ms
            if perf:
                perf.record(latency)
            ai_logger.info(f"perf_e2e latency_ms={latency:.2f} psid_hash={user_hash[:8]}... mid={rid}")
            ai_logger.info(f"ai_path_exit psid_hash={user_hash[:8]}... mid={rid} intents=['fallback'] mode=ERR")
            
            # Final fallback
            response = "Got it. Try 'summary' for a quick recap of your spending."
            return self._format_response(response), "fallback_error", None, None
    
    def _handle_ai_expense_logging(self, parse_result: Dict[str, Any], psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle AI-parsed expense logging with multiple items"""
        try:
            from utils.db import save_expense
            # Using canonical psid_hash from top-level import
            
            expenses = parse_result["expenses"]
            item_count = parse_result["item_count"]
            
            logged_expenses = []
            total_logged = 0
            
            # Log each expense
            for expense_data in expenses:
                amount = expense_data["amount"]
                description = expense_data["description"]
                category = expense_data["category"]
                
                # Log the expense  
                result = save_expense(
                    user_identifier=psid_hash,  # Use the already computed hash
                    description=description,
                    amount=amount,
                    category=category,
                    platform='messenger',
                    original_message=parse_result["original_text"],
                    unique_id=f"{psid}-{amount}-{description[:10]}"
                )
                success = result.get('success', False)
                
                if success:
                    logged_expenses.append(f"{amount} for {description}")
                    total_logged += amount
            
            # Update user interaction count
            try:
                # Simple interaction count update without user_manager
                from models import User
                from app import db
                from utils.identity import psid_hash as psid_hash_func
                user_hash = psid_hash_func(psid)  # Compute the hash from PSID
                user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
                if user:
                    user.interaction_count = (user.interaction_count or 0) + 1
                    db.session.commit()
            except Exception as e:
                logger.warning(f"Failed to update user stats: {e}")
            
            # Generate personalized AI response based on the expenses
            if logged_expenses:
                if item_count == 1:
                    response = f"Logged {expenses[0]['amount']} for {expenses[0]['description']} in {expenses[0]['category']}. "
                else:
                    response = f"Logged {item_count} expenses totaling {total_logged}: {', '.join(logged_expenses[:2])}{'...' if len(logged_expenses) > 2 else ''}. "
                
                # Add AI insight
                category_counts = {}
                for exp in expenses:
                    cat = exp["category"]
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                
                if len(category_counts) > 1:
                    response += f"Nice variety across {', '.join(category_counts.keys())}!"
                elif total_logged > 500:
                    response += "That's a significant amount - tracking helps you stay aware!"
                else:
                    response += "Great job tracking your spending!"
                
                # Ensure user_hash is properly bound for logging  
                from utils.identity import psid_hash as psid_hash_func
                user_hash = psid_hash_func(psid)
                self._log_routing_decision(rid, user_hash, "ai_multi_expense", f"logged_{item_count}_items_total_{total_logged}")
                return self._format_response(response), "ai_expense_logged", expenses[0]["category"] if expenses else None, total_logged
            else:
                response = "I couldn't log those expenses. Try a simpler format like 'coffee 100'."
                return self._format_response(response), "expense_error", None, None
                
        except Exception as e:
            logger.error(f"AI expense logging error: {e}")
            response = "Got it! I'll track that spending for you."
            return self._format_response(response), "expense_fallback", None, None
    
    def _handle_onboarding(self, text: str, psid: str, user_data: Dict[str, Any], rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle user onboarding with complete AI-driven system"""
        from utils.ai_onboarding_system import ai_onboarding_system
        from utils.identity import psid_hash
        
        user_hash = psid_hash(psid)
        
        try:
            # Use AI to process the user's response and determine next steps
            response_text, updated_user_data = ai_onboarding_system.process_user_response(text, user_data)
            
            # Update the database with AI-extracted data directly
            from models import User
            from app import db
            user_hash_value = user_hash  # Use the already computed hash from above
            # Guard against model regressions
            assert hasattr(User, "user_id_hash"), "User model must expose user_id_hash"
            user = db.session.query(User).filter_by(user_id_hash=user_hash_value).first()
            if not user:
                # Create new user - using correct field name
                user = User()
                user.user_id_hash = user_hash_value
                user.platform = 'messenger'
                db.session.add(user)
            
            # Update onboarding fields
            for key, value in updated_user_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            success = True
            try:
                db.session.commit()
            except Exception as e:
                logger.warning(f"Failed to update user onboarding: {e}")
                db.session.rollback()
                success = False
            
            if not success:
                logger.warning(f"Failed to update user data during AI onboarding: {user_hash_value[:8]}...")
                response_text = "Let me help you get started. What's your monthly income range?"
            
            # Check if onboarding is complete
            if updated_user_data.get('has_completed_onboarding', False):
                self._log_routing_decision(rid, user_hash_value, "onboarding_complete", "ai_driven_completion")
                return self._format_response(response_text), "onboarding_complete", None, None
            else:
                current_step = updated_user_data.get('onboarding_step', 0)
                self._log_routing_decision(rid, user_hash_value, "onboarding", f"ai_step_{current_step}")
                return self._format_response(response_text), "onboarding", None, None
                
        except Exception as e:
            logger.error(f"AI onboarding error: {e}")
            # Fallback to simple onboarding progression
            fallback_response = "I'm here to help you track your finances. What's your monthly income range?"
            # Compute hash for fallback logging
            from utils.identity import psid_hash as psid_hash_func
            fallback_hash = psid_hash_func(psid)
            self._log_routing_decision(rid, fallback_hash, "onboarding_fallback", "ai_error")
            return self._format_response(fallback_response), "onboarding", None, None
    
    def _handle_uat_commands(self, text: str, psid: str, rid: str) -> Optional[Tuple[str, str, Optional[str], Optional[float]]]:
        """Handle UAT system commands"""
        from utils.uat_system import uat_system
        from utils.identity import psid_hash
        
        user_hash = psid_hash(psid)
        text_lower = text.lower().strip()
        
        # Start UAT command
        if text_lower in ['start uat', 'begin uat', 'uat start', 'test bot']:
            response = uat_system.start_uat(psid, "Live Tester")
            self._log_routing_decision(rid, user_hash, "uat_start", "initiated")
            return self._format_response(response), "uat_initiated", None, None
        
        # UAT stats command
        elif text_lower in ['uat stats', 'uat status']:
            stats = uat_system.get_uat_stats()
            response = f"UAT Stats: {stats['active_uat_sessions']} active sessions"
            self._log_routing_decision(rid, user_hash, "uat_stats", "requested")
            return self._format_response(response), "uat_stats", None, None
        
        return None
    
    def _handle_uat_flow(self, text: str, psid: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle active UAT testing flow"""
        from utils.uat_system import uat_system
        from utils.identity import psid_hash
        
        user_hash = psid_hash(psid)
        
        # Get next UAT prompt
        uat_response = uat_system.get_next_uat_prompt(psid, text)
        
        if uat_response:
            self._log_routing_decision(rid, user_hash, "uat_flow", "step_completed")
            return self._format_response(uat_response), "uat_testing", None, None
        else:
            # UAT completed, fall back to normal routing
            return self._format_response("UAT completed. Normal bot operation resumed."), "uat_completed", None, None
    
    def _format_response(self, text: str) -> str:
        """Format response with 280 character limit and graceful clipping"""
        if len(text) <= 280:
            return text
        
        # Graceful clipping with continuation indicator
        clipped = text[:276] + "…"
        if clipped.endswith("?\n…"):
            clipped = clipped[:-3] + "… Want details?"
        elif clipped.endswith(".\n…"):
            clipped = clipped[:-3] + "… More?"
        
        return clipped
    
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
            
            user_hash = psid_hash(psid)
            
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
            from sqlalchemy import text
            from datetime import datetime, timedelta
            
            user_hash = psid_hash(psid)
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
    
    def _generate_ai_logged_response(self, amount: float, note: str, category: str, tips: List[str]) -> str:
        """Generate AI-powered response for logged expenses"""
        
        # Base confirmation with amount and note
        response = f"Logged: ৳{amount:.2f}"
        
        # Add note if present
        if note.strip():
            response += f" — {note}"
        
        # Add category insight
        if category != 'other':
            response += f" ({category})"
        
        # Add AI tip if available (keep it concise for Messenger)
        if tips and tips[0]:
            tip = tips[0][:60]  # Truncate to 60 chars for Messenger
            if not tip.endswith('.'):
                tip += '.'
            response += f". {tip}"
        else:
            # Default encouragement
            response += ". Nice."
        
        # Add summary prompt
        response += " Type summary anytime."
        
        return response
    
    def _undo_last_expense(self, psid: str) -> Optional[Tuple[float, str]]:
        """Undo last expense for user"""
        try:
            from app import db
            from models import Expense, User
            
            user_hash = psid_hash(psid)
            
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

    def _handle_unified_log(self, text: str, psid: str, psid_hash: str, rid: str, parsed_data: Dict) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle expense logging with unified parser and idempotency protection"""
        try:
            amount = parsed_data['amount']
            currency = parsed_data['currency']
            category = parsed_data['category']
            note = parsed_data['note']
            
            # Store expense with idempotency protection using Facebook message ID (rid)
            from utils.db import save_expense_idempotent
            result = save_expense_idempotent(
                user_identifier=psid_hash,
                description=f"{category} expense",
                amount=float(amount),
                category=category,
                currency=currency,
                platform="facebook",
                original_message=text,
                unique_id=rid  # Use Facebook message ID for idempotency
            )
            
            if result.get('duplicate'):
                # Return duplicate message with timestamp
                timestamp = result.get('timestamp', 'earlier')
                response = f"Looks like a repeat—already logged at {timestamp}. Reply 'yes' to log again."
                return normalize(response), "log_duplicate", category, float(amount)
            
            # Generate success response
            currency_symbol = '৳' if currency == 'BDT' else '$' if currency == 'USD' else '€' if currency == 'EUR' else '£' if currency == 'GBP' else '₹'
            response = f"✅ Logged: {currency_symbol}{amount:.0f} for {category}"
            
            self._log_routing_decision(rid, psid_hash, "log", f"unified_logged: {amount} {currency} {category}")
            return normalize(response), "log", category, float(amount)
            
        except Exception as e:
            logger.error(f"Unified log error: {e}")
            response = "Unable to log expense. Please try again."
            return normalize(response), "error", None, None
    
    def _emit_structured_telemetry(self, rid: str, psid_hash: str, intent: str, reason: str, data: Dict):
        """Emit structured telemetry for tracking and debugging"""
        try:
            # Create structured telemetry entry
            telemetry_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'request_id': rid,
                'psid_hash': psid_hash[:8] + "...",  # Truncated for privacy
                'intent': intent,
                'reason': reason,
                **data
            }
            
            # Log structured data for analytics
            logger.info(f"TELEMETRY: {telemetry_data}")
            
            # Emit to specialized telemetry system if available
            try:
                from finbrain.structured import emit_telemetry
                emit_telemetry(telemetry_data)
            except ImportError:
                # Telemetry system not available, just log
                pass
                
        except Exception as e:
            logger.warning(f"Telemetry emission error: {e}")
            # Never fail the main flow for telemetry issues
    
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
                'MAX_REPLY_LEN': int(os.environ.get("MAX_REPLY_LEN", "560")),  # Doubled from 280 to 560 chars
                'PANIC_PLAIN_REPLY': PANIC_PLAIN_REPLY
            }
        }
    
    def get_trace_logs(self) -> List[Dict[str, Any]]:
        """Get recent routing decisions for trace analysis"""
        # For now, return empty list since we log to structured JSON
        # In production, this would integrate with log aggregation
        return []

# Global instance
production_router = ProductionRouter()

# Flask Blueprint for webhook endpoints
webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook/messenger', methods=['GET', 'POST'])
def webhook_messenger():
    """Facebook Messenger webhook endpoint"""
    if request.method == 'GET':
        # Webhook verification
        verify_token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if verify_token == os.environ.get('FACEBOOK_VERIFY_TOKEN'):
            return challenge
        return 'Verification failed', 403
    
    elif request.method == 'POST':
        # Process incoming message
        data = request.get_json()
        if not data or data.get('object') != 'page':
            return jsonify({'status': 'ok'})
        
        # Extract events and process
        for entry in data.get('entry', []):
            for message_event in entry.get('messaging', []):
                if 'message' in message_event and 'text' in message_event['message']:
                    # Extract PSID with fallback
                    psid = message_event.get('sender', {}).get('id')
                    if not psid:
                        continue  # Skip if no PSID
                    
                    text = message_event['message']['text']
                    mid = message_event['message'].get('mid', 'unknown')
                    rid = get_request_id() or mid
                    
                    # Route message through production router
                    response, intent, category, amount = production_router.route_message_engagement(text, psid, rid)
                    
                    # Send response (simplified for testing)
                    return jsonify({
                        'recipient': {'id': psid},
                        'message': {'text': response[:2000]}  # Facebook limit
                    })
        
        return jsonify({'status': 'ok'})