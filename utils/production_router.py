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

# Money detection and unified parsing (enhanced)
from finbrain.router import contains_money
from parsers.expense import parse_amount_currency_category, parse_expense as parse_expense_enhanced

# SMART_NLP_ROUTING and SMART_CORRECTIONS system components
from utils.feature_flags import is_smart_nlp_enabled, is_smart_tone_enabled, is_smart_corrections_enabled
from utils.structured import log_routing_decision, log_money_detection_fallback
from parsers.expense import is_correction_message
from finbrain.router import contains_money_with_correction_fallback
# Lazy import for handle_correction to break circular dependency
# from handlers.expense import handle_correction

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

# FAQ/Smalltalk guardrail imports
from utils.faq_map import match_faq_or_smalltalk, fallback_default

# Messaging guardrails imports
from utils.ttl_store import get_store
from utils.ux_copy import (
    SLOW_DOWN, DAILY_LIMIT, REPEAT_HINT, PII_WARNING, BUSY, FALLBACK
)

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

# Audit transparency feature flag check
def _is_audit_ui_enabled() -> bool:
    """Check if audit UI is enabled"""
    try:
        from utils.pca_feature_flags import pca_feature_flags
        return pca_feature_flags.should_show_audit_ui()
    except:
        return False

# Summary detection patterns (Enhanced for Bengali + comprehensive English)
SUMMARY_RE = re.compile(
    r"\b(summary|recap|overview|report|what did i spend|how much did i spend|show (me )?my (spend|spending|expenses)|how much.*spend.*week|how much.*spend.*month|spending.*week|spending.*month)\b|সারাংশ|খরচের.*সারাংশ|মাসের.*খরচ|আমার.*খরচ|কত.*খরচ.*করেছি",
    re.IGNORECASE,
)

def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def _is_summary_command(text: str) -> bool:
    if not text:
        return False
    
    # Enhanced summary detection with Bengali support
    bengali_summary_terms = ["সারাংশ", "খরচের সারাংশ", "মাসের খরচ", "আমার খরচ", "কত খরচ করেছি"]
    english_summary_terms = {"summary", "recap", "report", "overview", "show my spending", "spending summary"}
    
    normalized = _norm_text(text)
    
    return (bool(SUMMARY_RE.search(text)) or 
            normalized in english_summary_terms or
            any(term in text for term in bengali_summary_terms))

def handle_summary(psid: str, text: str):
    """Deterministic summary handler with timeframe detection"""
    # Detect timeframe from user message
    text_lower = text.lower() if text else ""
    
    # Default to week, but check for month indicators
    timeframe = "week"
    if any(keyword in text_lower for keyword in ["month", "monthly", "this month", "months"]):
        timeframe = "month"
    elif any(keyword in text_lower for keyword in ["week", "weekly", "last week", "this week"]):
        timeframe = "week"
    
    # Use proper summary handler with timeframe support
    try:
        from handlers.summary import handle_summary as proper_handler
        result = proper_handler(psid, timeframe)
        return result.get('text', 'Unable to generate summary at this time.')
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
        
        # In-memory store for previous bot intents (for intent upgrade detection)
        # In production, this could be Redis or database-backed
        self._previous_intents = {}
    
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
        
        # ANALYTICS: Track user activity (100% additive, fail-safe)
        try:
            from utils.lightweight_analytics import track_user_activity
            from models import User
            user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
            is_new_user = user is None or user.is_new if user else False
            track_user_activity(user_hash, is_new_user)
        except Exception as e:
            # Fail-safe: analytics errors never break message processing
            logger.debug(f"Analytics tracking failed: {e}")
        
        try:
            # Always log router banner with current config
            from utils.config import FEATURE_FLAGS_VERSION
            logger.info(f"[ROUTER] mode=AI features=[NLP_ROUTING,TONE,CORRECTIONS] config_version={FEATURE_FLAGS_VERSION} psid={psid[:8]}...")
            
            # Panic mode - immediate acknowledgment
            if PANIC_PLAIN_REPLY:
                response = normalize("OK")
                self._log_routing_decision(rid, user_hash, "panic", "immediate_ack")
                return response, "panic", None, None
            
            
            # Step 0: FAQ/SMALLTALK GUARDRAIL - Deterministic responses with emojis (no AI)
            faq_response = match_faq_or_smalltalk(text)
            if faq_response:
                self._log_routing_decision(rid, user_hash, "faq_smalltalk", "deterministic")
                self._record_processing_time(time.time() - start_time)
                return faq_response, "faq", None, None
            
            # Step 0.5: MESSAGING GUARDRAILS - Post-FAQ safety checks (fail-open design)
            try:
                guardrail_response = self._check_messaging_guardrails(text, user_hash, rid)
                if guardrail_response:
                    self._log_routing_decision(rid, user_hash, "messaging_guardrail", "safety_triggered")
                    self._record_processing_time(time.time() - start_time)
                    return guardrail_response, "guardrail", None, None
            except Exception as e:
                # Fail-open: guardrail errors never break message flow
                logger.warning(f"Messaging guardrail check failed (user={user_hash[:8]}): {e}")
            
            # Step 0.7: REMINDER INTENT DETECTION - Check for reminder-related messages
            try:
                from handlers.reminders import detect_reminder_intent
                reminder_response = detect_reminder_intent(user_hash, text)
                if reminder_response:
                    self._log_routing_decision(rid, user_hash, "reminder", reminder_response['intent'])
                    self._record_processing_time(time.time() - start_time)
                    return normalize(reminder_response['text']), reminder_response['intent'], reminder_response.get('category'), reminder_response.get('amount')
            except Exception as e:
                # Fail-open: reminder errors never break message flow
                logger.warning(f"Reminder detection failed (user={user_hash[:8]}): {e}")
            
            # Step 0.8: PROBLEM REPORTING - Catch issues before they become negative reviews
            # Canary control: can be disabled via ENABLE_PROBLEM_REPORTING=false
            if os.getenv('ENABLE_PROBLEM_REPORTING', 'true').lower() == 'true':
                try:
                    if self._detect_problem_report(text):
                        problem_response = self._handle_problem_report(user_hash, text)
                        self._log_routing_decision(rid, user_hash, "problem_report", "ticket_logged")
                        self._record_processing_time(time.time() - start_time)
                        return normalize(problem_response), "problem_report", None, None
                except Exception as e:
                    # Fail-open: problem reporting errors never break message flow
                    logger.warning(f"Problem reporting failed (user={user_hash[:8]}): {e}")
            
            # Step 1: LEARNING INTENT DETECTION FIRST (before correction)
            if self._is_learning_intent(text):
                logger.info(f"[ROUTER] Learning intent detected: '{text[:50]}...'")
                try:
                    response = self._handle_learning_intent(text, user_hash, rid)
                    self._log_routing_decision(rid, user_hash, "learning", "category_learned")
                    self._record_processing_time(time.time() - start_time)
                    return response, "learning_applied", None, None
                except Exception as e:
                    logger.warning(f"Learning intent handling failed: {e}")
            
            # Step 1.3: SUMMARY/ANALYSIS DETECTION (BEFORE AI processing)
            if _is_summary_command(text):
                logger.info(f"[ROUTER] Summary command detected: '{text[:50]}...'")
                try:
                    summary_response = handle_summary(psid, text)
                    self._log_routing_decision(rid, user_hash, "summary", "analysis_provided")
                    self._record_processing_time(time.time() - start_time)
                    return normalize(summary_response), "analysis", None, None
                except Exception as e:
                    logger.error(f"Summary handler error: {e}")
                    # Fall through to other handlers if summary fails
            
            # Step 1.5: DETERMINISTIC ROUTING (PoR v1.1 - EXPENSE_LOG and CLARIFY_EXPENSE intents)
            try:
                from utils.routing_policy import deterministic_router
                
                # Extract signals for routing decision
                signals = deterministic_router.extract_signals(text, user_hash)
                
                # Check if deterministic routing should be used
                if deterministic_router.should_use_deterministic_routing(signals):
                    routing_result = deterministic_router.route_intent(text, signals)
                    
                    # Handle EXPENSE_LOG intent
                    if routing_result.intent.value == "EXPENSE_LOG":
                        logger.info(f"[ROUTER] EXPENSE_LOG intent detected: '{text[:50]}...'")
                        try:
                            from expense_log_handlers import handle_expense_log_intent
                            expense_result = handle_expense_log_intent(user_hash, text, signals.__dict__)
                            
                            if expense_result['success']:
                                self._log_routing_decision(rid, user_hash, "expense_log", "logged_successfully")
                                self._record_processing_time(time.time() - start_time)
                                return normalize(expense_result['response']), "expense_log", expense_result.get('category'), expense_result.get('amount')
                            else:
                                logger.warning("EXPENSE_LOG processing failed, falling through")
                        except Exception as e:
                            logger.error(f"EXPENSE_LOG handler failed: {e}")
                    
                    # Handle CLARIFY_EXPENSE intent
                    elif routing_result.intent.value == "CLARIFY_EXPENSE":
                        logger.info(f"[ROUTER] CLARIFY_EXPENSE intent detected: '{text[:50]}...'")
                        try:
                            from expense_log_handlers import handle_clarify_expense_intent
                            clarify_result = handle_clarify_expense_intent(user_hash, text, signals.__dict__)
                            
                            if clarify_result['success']:
                                self._log_routing_decision(rid, user_hash, "clarify_expense", "prompted")
                                self._record_processing_time(time.time() - start_time)
                                return normalize(clarify_result['response']), "clarify_expense", None, None
                            else:
                                logger.warning("CLARIFY_EXPENSE processing failed, falling through")
                        except Exception as e:
                            logger.error(f"CLARIFY_EXPENSE handler failed: {e}")
                    
                    # For other deterministic intents (ANALYSIS, FAQ, COACHING), continue to existing handlers
                    logger.debug(f"Deterministic routing returned {routing_result.intent.value}, continuing to existing handlers")
                
            except Exception as e:
                logger.warning(f"Deterministic routing failed: {e}, falling back to legacy routing")
            
            # Step 2: CORRECTION DETECTION - After learning check
            if is_correction_message(text):
                logger.info(f"[ROUTER] Correction detected: user={user_hash[:8]}...")
                
                # Handle correction flow (always enabled)
                try:
                    from handlers.expense import handle_correction  # Lazy import to avoid circular dependency
                    correction_result = handle_correction(user_hash, rid, text, datetime.utcnow())
                    
                    self._emit_structured_telemetry(rid, user_hash, "CORRECTION", "processed", {
                        'corrections_always_on': True,
                        'intent_result': correction_result.get('intent'),
                        'amount': correction_result.get('amount'),
                        'category': correction_result.get('category')
                    })
                    
                    self._record_processing_time(time.time() - start_time)
                    return (
                        normalize(correction_result['text']),
                        correction_result['intent'],
                        correction_result.get('category'),
                        correction_result.get('amount')
                    )
                    
                except Exception as e:
                    logger.error(f"Correction handling failed: {e}")
                    # Fall through to regular expense logging as fallback
                    
            # Step 2: AI ROUTING FIRST - Enhanced with CC Decision Tree (Phase 2)
            # Check if this looks like an expense for AI routing
            money_detected = contains_money_with_correction_fallback(text, user_hash)
            
            if money_detected:
                # Try CC-based AI routing first (always enabled)
                try:
                    cc_result = self._route_cc_decision(text, psid, user_hash, rid)
                    if cc_result:
                        response, intent, category, amount = cc_result
                        self._emit_structured_telemetry(rid, user_hash, "LOG", "cc_routing_success", {
                            'amount': amount,
                            'category': category,
                            'cc_enabled': True
                        })
                        self._record_processing_time(time.time() - start_time)
                        return normalize(response), intent, category, amount
                    else:
                        logger.debug("CC routing returned no result, falling back to legacy AI")
                        
                except Exception as e:
                    logger.error(f"CC routing failed: {e}, falling back to legacy AI")
                
                # Legacy AI fallback if CC routing fails
                try:
                    from handlers.expense import handle_multi_expense_logging
                    result = handle_multi_expense_logging(user_hash, rid, text, datetime.utcnow())
                    
                    if result.get('intent') in ['log_single', 'log_multi']:
                        self._emit_structured_telemetry(rid, user_hash, "LOG", "legacy_ai_fallback", {
                            'amount': result.get('amount'),
                            'category': result.get('category'),
                            'multi_expense': result.get('intent') == 'log_multi'
                        })
                        self._record_processing_time(time.time() - start_time)
                        return normalize(result['text']), result['intent'], result.get('category'), result.get('amount')
                    else:
                        # AI couldn't parse, fall through to regex
                        logger.warning(f"Legacy AI parsing failed, falling back to regex for: {text[:50]}...")
                        
                except Exception as e:
                    logger.error(f"Legacy AI routing failed: {e}, falling back to regex")
                
                # Legacy fallback only if AI fails  
                parsed_data = parse_amount_currency_category(text)
                if parsed_data and parsed_data.get('amount'):
                    response, intent, category, amount = self._handle_unified_log(text, psid, user_hash, rid, parsed_data)
                    self._emit_structured_telemetry(rid, user_hash, "LOG", "legacy_fallback", {
                        'amount': float(parsed_data['amount']),
                        'currency': parsed_data['currency'],
                        'category': parsed_data['category']
                    })
                    self._record_processing_time(time.time() - start_time)
                    return response, intent, category, amount
            
            # Step 3: PoR v1.1 Deterministic Routing Layer
            from utils.routing_policy import deterministic_router
            
            # Extract user signals for deterministic routing
            user_signals = deterministic_router.extract_signals(text, user_hash)
            
            # Check if we should use deterministic routing based on scope
            if deterministic_router.should_use_deterministic_routing(user_signals):
                # Use deterministic routing
                routing_result = deterministic_router.route_intent(text, user_signals)
                deterministic_router.log_routing_decision(user_hash, text, routing_result, rid)
                
                # Map deterministic intent to legacy intent for compatibility
                intent_mapping = {
                    "ADMIN": "DIAGNOSTIC",
                    "PCA_AUDIT": "SUMMARY", 
                    "ANALYSIS": "INSIGHT",
                    "FAQ": "FAQ",
                    "COACHING": "COACHING",
                    "SMALLTALK": "FAQ"
                }
                intent = intent_mapping.get(routing_result.intent.value, "FAQ")
                
                logger.info(f"[ROUTER] Deterministic routing: {routing_result.intent.value} → {intent} "
                           f"(confidence={routing_result.confidence:.2f}, reasons={routing_result.reason_codes})")
            else:
                # Fallback to legacy intent detection
                from utils.intent_router import detect_intent
                intent = detect_intent(text)
                logger.info(f"[ROUTER] Legacy AI routing: {intent} (scope={deterministic_router.flags.scope.value})")
            
            # Continue with existing intent upgrade logic
            from utils.intent_router import is_followup_after_summary_or_log
            
            # Step 3.1: Handle category-specific breakdown queries
            if intent == "CATEGORY_BREAKDOWN":
                try:
                    from handlers.category_breakdown import handle_category_breakdown
                    result = handle_category_breakdown(user_hash, text)
                    response = result.get('text', 'Unable to get category breakdown')
                    self._emit_structured_telemetry(rid, user_hash, "CATEGORY", "breakdown_success", {})
                    self._log_routing_decision(rid, user_hash, "category", "breakdown_provided")
                    self._record_processing_time(time.time() - start_time)
                    return normalize(response), "category_breakdown", None, None
                except Exception as e:
                    logger.error(f"Category breakdown failed: {e}")
                    # Fall through to regular summary as fallback
            upgrade_reason = None
            
            # Step 3.1: Check for intent upgrade (SUMMARY/LOG → INSIGHT)
            # This checks if user asks for insights after receiving summary/log response
            previous_intent = self._get_previous_bot_intent(user_hash)  # We'll implement this
            if intent == "INSIGHT" and is_followup_after_summary_or_log(text, previous_intent):
                upgrade_reason = "followup_after_" + (previous_intent.lower() if previous_intent else "unknown")
                logger.info(f"[ROUTER] INTENT_UPGRADE: {previous_intent}→INSIGHT reason={upgrade_reason}")
            elif intent == "INSIGHT" and any(keyword in text.lower() for keyword in ["analysis", "analyze", "advise", "advice", "suggest", "tips", "optimize", "insight", "breakdown", "review", "how am i doing", "help me save"]):
                upgrade_reason = "ask_keywords"
                logger.info(f"[ROUTER] INTENT_UPGRADE: UNKNOWN→INSIGHT reason=ask_keywords")
            
            # Step 3.5: Handle contradiction guard for spending increase requests
            if intent == "CLARIFY_SPENDING_INTENT":
                response = normalize("🤔 I want to make sure I help you the right way! Are you looking for tips to spend *less* and save more money, or do you actually want to increase your spending? Just want to point my advice in the right direction! 💡")
                self._emit_structured_telemetry(rid, user_hash, "CLARIFY", "spending_contradiction", {})
                self._log_routing_decision(rid, user_hash, "clarify", "spending_intent_contradiction")
                self._record_processing_time(time.time() - start_time)
                return response, "clarify", None, None
            
            # Step 4: Route non-AI intents immediately (bypass rate limits)
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
                
                # CRITICAL: Always send normal reply first, then check for optional coaching
                # This implements intent-first short-circuit per hardening requirements
                normal_reply = normalize(response_text)
                
                # Record the successful normal reply with upgrade reason if applicable
                telemetry_data = {}
                if upgrade_reason:
                    telemetry_data["upgrade_reason"] = upgrade_reason
                self._emit_structured_telemetry(rid, user_hash, intent, "deterministic_bypass", telemetry_data)
                self._log_routing_decision(rid, user_hash, intent.lower(), "deterministic_bypass")
                
                # Store current intent for future upgrade detection
                self._store_previous_bot_intent(user_hash, intent)
                
                # For protected intents (SUMMARY), NEVER attempt coaching - return immediately
                if intent in ["SUMMARY"]:
                    from utils.structured import log_structured_event
                    log_structured_event("COACH_SKIPPED_INTENT", {
                        "intent": intent,
                        "reason": intent.lower()
                    })
                    return normal_reply, intent.lower(), None, None
                
                # For INSIGHT only: Check if we should append coaching as SECOND message
                # This is now safe because normal reply is already composed
                # DISABLED: This was causing duplicate AI responses - insights already generated above
                # if intent == "INSIGHT" and text.lower().strip() == "insight":
                #     try:
                #         from handlers.coaching import maybe_continue
                #         coaching_reply = maybe_continue(user_hash, intent.lower(), {
                #             'original_text': text
                #         })
                #         if coaching_reply:
                #             # Send normal reply first, then coaching as separate message
                #             # For now, return coaching reply - TODO: implement dual message sending
                #             return normalize(coaching_reply['text']), coaching_reply['intent'], coaching_reply.get('category'), coaching_reply.get('amount')
                #     except Exception as e:
                #         logger.error(f"[COACH][ERROR] Optional coaching failed: {e}")
                #         # Continue with normal response - coaching failure doesn't break normal flow
                
                return normal_reply, intent.lower(), None, None
            
            # Step 5: Check for active coaching session first
            try:
                from handlers.coaching import handle_coaching_response
                coaching_reply = handle_coaching_response(user_hash, text)
                if coaching_reply:
                    # User is in active coaching session
                    self._emit_structured_telemetry(rid, user_hash, "COACHING", "session_response", {})
                    self._log_routing_decision(rid, user_hash, "coaching", "session_active")
                    self._record_processing_time(time.time() - start_time)
                    return normalize(coaching_reply['text']), coaching_reply['intent'], coaching_reply.get('category'), coaching_reply.get('amount')
            except Exception as e:
                logger.error(f"[COACH][ERROR] Session check failed: {e}")
                # Continue with normal flow
            
            # Step 6: Handle expense logging with new parser
            if intent == "LOG_EXPENSE":
                from handlers.logger import handle_log
                result = handle_log(user_hash, text)
                response = result.get('text', 'Unable to log expense')
                self._emit_structured_telemetry(rid, user_hash, "LOG", "intent_log_expense", {})
                self._log_routing_decision(rid, user_hash, "log", "expense_logged")
                self._record_processing_time(time.time() - start_time)
                return normalize(response), "log", None, None
            
            # Step 6: Evaluate rate limiter for AI paths only
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
            
            # Step 8: AI-Enhanced FAQ Detection (NEW)
            logger.info(f"[ROUTER] Unknown intent detected, checking AI FAQ: '{text[:50]}...'")
            try:
                from utils.ai_faq_classifier import ai_enhanced_faq_detection
                faq_response = ai_enhanced_faq_detection(text)
                if faq_response:
                    # Found FAQ match - return FAQ response
                    logger.info(f"[ROUTER] AI FAQ detection successful")
                    self._log_routing_decision(rid, user_hash, "ai_faq", "faq_detected")
                    self._record_processing_time(time.time() - start_time)
                    return normalize(faq_response), "faq", None, None
            except Exception as faq_error:
                logger.warning(f"AI FAQ detection failed: {faq_error}")
                # Continue to fallback - no interruption to normal flow
            
            # Step 9: Learning intent already checked at Step 1
            
            # Step 10: Check for clarification responses
            logger.info(f"[ROUTER] Checking for clarification response: '{text[:50]}...'")
            try:
                from utils.expense_clarification import expense_clarification_handler
                clarification_result = expense_clarification_handler.handle_clarification_response(user_hash, text)
                
                if clarification_result:
                    if clarification_result['success']:
                        # User provided clarification - complete the expense logging
                        original_expense = clarification_result['original_expense']
                        final_category = clarification_result['category']
                        
                        # Save the expense with the clarified category
                        from utils.db import save_expense
                        save_expense(
                            user_identifier=user_hash,
                            description=f"{final_category} expense",
                            amount=original_expense["amount"],
                            category=final_category,
                            platform="facebook",
                            original_message=original_expense["original_text"],
                            unique_id=rid
                        )
                        
                        response = normalize(clarification_result['message'])
                        self._log_routing_decision(rid, user_hash, "clarification_completed", f"learned_{final_category}")
                        self._record_processing_time(time.time() - start_time)
                        return response, "expense_clarified", final_category, original_expense["amount"]
                    else:
                        # Clarification failed - ask again
                        response = normalize(clarification_result['message'])
                        self._log_routing_decision(rid, user_hash, "clarification_retry", "unclear_response")
                        self._record_processing_time(time.time() - start_time)
                        return response, "clarification_retry", None, None
            except Exception as e:
                logger.warning(f"Clarification response handling failed: {e}")
            
            # Step 10: Unknown intent - route to AI for natural conversation
            logger.info(f"[ROUTER] No FAQ/clarification match, routing to AI conversation: '{text[:50]}...'")
            try:
                # Try AI-powered natural conversation (NOT expense parsing)
                response, intent, category, amount = self._route_ai_conversation(text, psid, user_hash, rid, rate_limit_result)
                self.telemetry['ai_messages'] += 1
                self._log_routing_decision(rid, user_hash, "ai_conversation", "natural_chat")
                self._record_processing_time(time.time() - start_time)
                return response, intent, category, amount
            except Exception as e:
                logger.warning(f"AI conversation failed for unknown intent: {e}")
                # Last resort fallback with engaging tone
                response = "🤔 I'm not sure what you're looking for, but I can help with expenses! Try asking about your spending this week or logging a new expense."
                self._log_routing_decision(rid, user_hash, "help_enhanced", "unknown_intent_final")
                self._record_processing_time(time.time() - start_time)
                return normalize(response), "help", None, None
            
        except Exception as e:
            logger.error(f"Production routing error: {e}")
            # Emergency fallback with friendly FAQ default
            response = fallback_default()
            self._log_routing_decision(rid, user_hash, "error", f"emergency_fallback: {str(e)}")
            return response, "error", None, None
    
    
    def _is_learning_intent(self, text: str) -> bool:
        """Detect if user is trying to teach category preferences - COMPREHENSIVE PATTERNS"""
        text_lower = text.lower().strip()
        
        # EXPANDED learning patterns to catch ALL natural language
        learning_patterns = [
            # Basic patterns (existing)
            r'(\w+)\s+is\s+(food|drink|transport|shopping|health|entertainment)',
            r'(\w+)\s+should\s+be\s+(food|drink|transport|shopping|health|entertainment)',
            r'log\s+(\w+)\s+under\s+(food|drink|transport|shopping|health|entertainment)',
            r'categorize\s+(\w+)\s+as\s+(food|drink|transport|shopping|health|entertainment)',
            r'(\w+)\s+belongs\s+to\s+(food|drink|transport|shopping|health|entertainment)',
            
            # Natural language patterns (ADDED FOR STAKEHOLDERS)
            r'(\w+)\s+should\s+be\s+categorized\s+under\s+(food|drink|transport|shopping|health|entertainment)',
            r'(\w+)\s+needs?\s+to\s+go\s+under\s+(food|drink|transport|shopping|health|entertainment)',
            r'put\s+(\w+)\s+(in|under)\s+the\s+(food|drink|transport|shopping|health|entertainment)\s+category',
            r'(\w+)\s+expenses?\s+(should\s+)?go\s+(in|under)\s+(food|drink|transport|shopping|health|entertainment)',
            r'can\s+you\s+(please\s+)?put\s+(\w+)\s+.*(food|drink|transport|shopping|health|entertainment)',
            r'i\s+think\s+(\w+)\s+should\s+be\s+.*(food|drink|transport|shopping|health|entertainment)',
            r'you\s+need\s+to\s+log\s+(\w+)\s+under\s+(food|drink|transport|shopping|health|entertainment)',
            
            # Correction-style learning
            r'(\w+)\s+(needs|should)\s+to\s+be\s+(food|drink|transport|shopping|health|entertainment)',
            r'that\s+(\w+)\s+should\s+have\s+been\s+(food|drink|transport|shopping|health|entertainment)',
            r'(\w+)\s+belongs\s+in\s+(food|drink|transport|shopping|health|entertainment)',
        ]
        
        import re
        for pattern in learning_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _handle_learning_intent(self, text: str, user_hash: str, rid: str) -> str:
        """Handle user teaching category preferences"""
        import re
        
        text_lower = text.lower().strip()
        
        # Extract item and category
        patterns = [
            r'(\w+)\s+is\s+(food|drink|transport|shopping|health|entertainment)',
            r'(\w+)\s+should\s+be\s+(food|drink|transport|shopping|health|entertainment)',
            r'log\s+(\w+)\s+under\s+(food|drink|transport|shopping|health|entertainment)',
            r'categorize\s+(\w+)\s+as\s+(food|drink|transport|shopping|health|entertainment)',
            r'(\w+)\s+belongs\s+to\s+(food|drink|transport|shopping|health|entertainment)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                item = match.group(1)
                category = match.group(2)
                
                # Learn the preference
                from utils.expense_learning import user_learning_system
                learned = user_learning_system.learn_user_preference(
                    user_hash, item, category, {'context': text, 'manual_teaching': True}
                )
                
                if learned:
                    # Find and update recent expense if exists
                    self._update_recent_expense_category(user_hash, item, category)
                    
                    return normalize(f"Perfect! ✅ I've learned that {item} = {category.title()} for you. I'll remember this for future expenses!")
                else:
                    return normalize(f"Thanks for teaching me! I'll try to remember that {item} goes under {category.title()}.")
        
        return normalize("Got it! I'm here to help categorize your expenses better.")
    
    def _update_recent_expense_category(self, user_hash: str, item: str, category: str):
        """Update recent expense category if item matches"""
        try:
            from models import Expense
            from app import db
            from datetime import datetime, timedelta
            
            # Look for recent expenses (last 10 minutes) that might match
            recent_time = datetime.utcnow() - timedelta(minutes=10)
            recent_expenses = db.session.query(Expense).filter(
                Expense.user_id == user_hash,
                Expense.created_at >= recent_time,
                Expense.original_message.ilike(f'%{item}%')
            ).order_by(Expense.created_at.desc()).limit(3).all()
            
            for expense in recent_expenses:
                if expense.category.lower() in ['general', 'other'] and item.lower() in expense.original_message.lower():
                    expense.category = category.title()
                    expense.description = f"{category.title()} expense: {item}"
                    db.session.commit()
                    break
                    
        except Exception as e:
            logger.warning(f"Failed to update recent expense: {e}")
    
    def _check_messaging_guardrails(self, text: str, user_hash: str, rid: str) -> Optional[str]:
        """
        Post-FAQ messaging guardrails with fail-open design
        Checks: rate limiting, daily caps, repeat detection, PII, spam
        Returns guardrail message or None to continue normal processing
        """
        import hashlib
        import os
        
        # Feature flag check - fail open if disabled
        enabled = os.getenv("MESSAGING_GUARDRAILS_ENABLED", "false").lower() == "true"
        if not enabled:
            return None
            
        try:
            store = get_store()
            now_str = datetime.utcnow().strftime("%Y%m%d")
            
            # 1. BURST RATE LIMITING (5 messages per 10 seconds)
            burst_key = f"burst:{user_hash}"
            burst_count = store.incr(burst_key, ttl_seconds=10)
            burst_limit = int(os.getenv("GUARDRAIL_BURST_LIMIT", "5"))
            
            if burst_count > burst_limit:
                logger.info(f"[GUARDRAIL] Burst limit hit: user={user_hash[:8]} count={burst_count}")
                return SLOW_DOWN
            
            # 2. DAILY MESSAGE CAP (30 messages per day)
            daily_key = f"daily:{user_hash}:{now_str}"
            daily_count = store.incr(daily_key, ttl_seconds=86400)  # 24 hours
            daily_limit = int(os.getenv("GUARDRAIL_DAILY_LIMIT", "30"))
            
            if daily_count > daily_limit:
                logger.info(f"[GUARDRAIL] Daily limit hit: user={user_hash[:8]} count={daily_count}")
                return DAILY_LIMIT
            
            # 3. ANTI-REPEAT DETECTION (45 second window with MD5 hash)
            text_clean = text.strip().lower()[:100]  # Normalize and cap
            text_hash = hashlib.md5(text_clean.encode()).hexdigest()[:8]
            repeat_key = f"repeat:{user_hash}:{text_hash}"
            
            if store.exists(repeat_key):
                logger.info(f"[GUARDRAIL] Repeat detected: user={user_hash[:8]} hash={text_hash}")
                return REPEAT_HINT
            else:
                # Set 45-second repeat window
                repeat_window = int(os.getenv("GUARDRAIL_REPEAT_WINDOW", "45"))
                store.setex(repeat_key, repeat_window, 1)
            
            # 4. PII DETECTION (basic patterns)
            pii_patterns = [
                r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card
                r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',             # SSN
                r'\b\d{10,15}\b'                                # Long numbers
            ]
            
            import re
            for pattern in pii_patterns:
                if re.search(pattern, text):
                    logger.warning(f"[GUARDRAIL] PII detected: user={user_hash[:8]} pattern={pattern[:20]}...")
                    return PII_WARNING
            
            # All checks passed
            return None
            
        except Exception as e:
            # Fail-open: never break message flow due to guardrail errors
            logger.warning(f"[GUARDRAIL] Check failed (user={user_hash[:8]}): {e}")
            return None

    def _get_previous_bot_intent(self, user_hash: str) -> Optional[str]:
        """
        Get the previous bot intent for this user (for intent upgrade detection)
        Returns the last bot intent or None if not found
        """
        return self._previous_intents.get(user_hash)
    
    def _store_previous_bot_intent(self, user_hash: str, intent: str) -> None:
        """
        Store the current bot intent for future upgrade detection
        In production, this could be backed by Redis with TTL
        """
        self._previous_intents[user_hash] = intent.upper()
        
        # Keep only recent entries (simple cleanup)
        if len(self._previous_intents) > 1000:
            # Remove oldest entries, keep last 500
            items = list(self._previous_intents.items())[-500:]
            self._previous_intents = dict(items)
    
    def _handle_expense_log(self, parsed_expense, text: str, psid: str, psid_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Handle deterministic expense logging"""
        amount, description = parsed_expense
        category = categorize_expense(description)
        
        # Store expense deterministically
        self._store_expense_deterministic(psid, amount, description, category, text)
        
        # Generate response with audit transparency
        response = format_logged_response(amount, description, category)
        
        # Add audit transparency if enabled
        tx_id = f"{psid_hash[:8]}-{int(time.time())}"
        audit_info = self._get_audit_transparency_info(tx_id, psid, amount, category, description)
        if audit_info:
            response += f"\n{audit_info}"
        
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
            # Try AI parsing with conversational clarification
            from ai.expense_parse import parse_expense
            expense = parse_expense(text, user_hash=psid_hash, check_ambiguity=True)
            
            # Handle clarification if needed
            if expense.get('needs_clarification'):
                clarification_info = expense.get('clarification_info', {})
                clarification_message = clarification_info.get('message', 'I need clarification about this expense.')
                
                # Store the pending expense for later completion
                self._log_routing_decision(rid, psid_hash, "ai_clarification", "pending_user_response")
                
                response = normalize(clarification_message)
                return response, "clarification_needed", None, None
            
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
        
        # Safe access to expense data
        category = None
        amount = None
        if 'expense' in locals() and expense is not None:
            category = expense.get('category')
            amount = expense.get('amount')
        
        return response, "ai_expense_logged", category, amount
    
    def _route_cc_decision(self, text: str, psid: str, psid_hash: str, rid: str) -> Optional[Tuple[str, str, Optional[str], Optional[float]]]:
        """
        Route based on Canonical Command decision logic with Feature Flags/Kill Switch
        Implements 4-state PCA_MODE conditional flow: FALLBACK/SHADOW/DRYRUN/ON
        """
        try:
            from utils.ai_adapter_v2 import production_ai_adapter
            from utils.pca_flags import pca_flags, PCAMode
            from datetime import datetime
            
            # PHASE 0: Check PCA_MODE and apply conditional flow
            current_mode = pca_flags.mode
            logger.debug(f"CC routing with PCA_MODE={current_mode.value} for user={psid_hash[:8]}")
            
            # FALLBACK mode: Skip CC entirely, use legacy parser flow
            if current_mode == PCAMode.FALLBACK:
                logger.debug("PCA_MODE=FALLBACK: Skipping CC generation, using legacy flow")
                return None  # Falls back to legacy AI in production_router
            
            # Generate CC for SHADOW, DRYRUN, and ON modes
            ai_result = production_ai_adapter.ai_parse(text, {'user_id': psid_hash})
            
            # Check if we got a valid CC response
            if ai_result.get('failover') or 'decision' not in ai_result:
                logger.debug(f"No valid CC from AI: failover={ai_result.get('failover')}")
                return None
            
            # Extract CC data
            decision = ai_result.get('decision')
            confidence = ai_result.get('confidence', 0.0)
            ui_note = ai_result.get('ui_note', '')
            cc_id = ai_result.get('cc_id', f"cc_{rid[:8]}")
            
            # Extract slot data for expense logging
            slots = ai_result.get('slots', {})
            amount = slots.get('amount')
            category = slots.get('category')
            note = slots.get('note', '')
            merchant_text = slots.get('merchant_text', '')
            
            # ALWAYS persist CC snapshot for SHADOW, DRYRUN, ON modes
            if pca_flags.should_log_snapshots():
                self._persist_cc_snapshot(cc_id, psid_hash, text, ai_result, current_mode.value, rid)
            
            self._log_routing_decision(rid, psid_hash, "cc_decision", 
                                     f"mode={current_mode.value}, decision={decision}, conf={confidence:.2f}")
            
            # SHADOW mode: CC generated and persisted, but show legacy response to user
            if current_mode == PCAMode.SHADOW:
                logger.debug("PCA_MODE=SHADOW: CC persisted, returning None for legacy response")
                return None  # User sees legacy response, CC logged invisibly
            
            # DRYRUN mode: CC persisted + raw ledger write + "would log" message
            if current_mode == PCAMode.DRYRUN:
                return self._handle_dryrun_mode(decision, amount, category, note, merchant_text, 
                                              text, psid_hash, rid, ui_note)
            
            # ON mode: Full CC processing with raw + overlay writes
            if current_mode == PCAMode.ON:
                return self._handle_on_mode(decision, amount, category, note, merchant_text, 
                                          text, psid_hash, rid, ui_note, ai_result)
            
            # Should not reach here, but fail safe
            logger.warning(f"Unexpected PCA_MODE: {current_mode.value}")
            return None
                
        except Exception as e:
            logger.error(f"CC decision routing failed: {e}")
            return None
    
    def _persist_cc_snapshot(self, cc_id: str, user_hash: str, text: str, ai_result: dict, pca_mode: str, rid: str):
        """Persist CC snapshot to inference_snapshots table (append-only)"""
        try:
            from app import db
            from sqlalchemy import text
            from datetime import datetime
            import json
            
            # Create CC snapshot record
            db.session.execute(text("""
                INSERT INTO inference_snapshots 
                (cc_id, user_id, intent, slots_json, confidence, decision, clarifier_json,
                 model_version, processing_time_ms, source_text, ui_note, created_at, 
                 pca_mode, applied, error_message)
                VALUES 
                (:cc_id, :user_id, :intent, :slots_json, :confidence, :decision, :clarifier_json,
                 :model_version, :processing_time_ms, :source_text, :ui_note, :created_at,
                 :pca_mode, :applied, :error_message)
            """), {
                'cc_id': cc_id,
                'user_id': user_hash,
                'intent': ai_result.get('intent', 'LOG_EXPENSE'),
                'slots_json': json.dumps(ai_result.get('slots', {})),
                'confidence': ai_result.get('confidence', 0.0),
                'decision': ai_result.get('decision', 'RAW_ONLY'),
                'clarifier_json': json.dumps(ai_result.get('clarifier')),
                'model_version': ai_result.get('model_version', 'gemini-2.5-flash-lite'),
                'processing_time_ms': ai_result.get('processing_time_ms', 0),
                'source_text': text,
                'ui_note': ai_result.get('ui_note', ''),
                'created_at': datetime.utcnow(),
                'pca_mode': pca_mode,
                'applied': False,  # Will be updated when expense is saved
                'error_message': None
            })
            
            db.session.commit()
            logger.debug(f"CC snapshot persisted: {cc_id} (mode={pca_mode})")
            
        except Exception as e:
            logger.error(f"Failed to persist CC snapshot: {e}")
            # Don't fail the entire request if snapshot fails
            
    def _handle_dryrun_mode(self, decision: str, amount: float, category: str, note: str, 
                          merchant_text: str, text: str, user_hash: str, rid: str, ui_note: str):
        """Handle DRYRUN mode: Raw ledger write + 'would log' message"""
        try:
            if amount and amount > 0:
                # Write to RAW ledger only (no overlays)
                success = self._save_cc_expense_raw_only(user_hash, amount, category, note, merchant_text, text, rid)
                if success:
                    # DRYRUN "would log" message format
                    category_display = category or 'expense'
                    dryrun_message = f"✅ Saved ৳{amount:.0f}\n(Would log as {category_display})"
                    return dryrun_message, "log_dryrun", category, amount
                else:
                    return "Failed to save expense, please try again.", "error", None, None
            else:
                return ui_note or "I need an amount to log this expense.", "help", None, None
                
        except Exception as e:
            logger.error(f"DRYRUN mode handling failed: {e}")
            return "Processing failed, please try again.", "error", None, None
    
    def _handle_on_mode(self, decision: str, amount: float, category: str, note: str,
                       merchant_text: str, text: str, user_hash: str, rid: str, ui_note: str, ai_result: dict):
        """Handle ON mode: Full CC processing with raw + overlay writes"""
        try:
            from utils.pca_flags import pca_flags
            
            # Handle decision tree based on confidence
            if decision == "AUTO_APPLY":
                # High confidence - direct save with overlays
                if amount and amount > 0:
                    success = self._save_cc_expense_with_overlays(user_hash, amount, category, note, merchant_text, text, rid)
                    if success:
                        # Full audit UI response
                        return self._format_full_audit_response(amount, category, ui_note)
                    else:
                        return "Failed to log expense, please try again.", "error", None, None
                else:
                    return ui_note or "I need an amount to log this expense.", "help", None, None
                    
            elif decision == "ASK_ONCE":
                # Mid confidence - check clarifiers setting
                if not pca_flags.should_enable_clarifiers():
                    # Clarifiers disabled - auto-apply anyway
                    if amount and amount > 0:
                        success = self._save_cc_expense_with_overlays(user_hash, amount, category, note, merchant_text, text, rid)
                        if success:
                            return self._format_full_audit_response(amount, category, ui_note)
                        else:
                            return "Failed to log expense, please try again.", "error", None, None
                    else:
                        return ui_note or "I need an amount to log this expense.", "help", None, None
                else:
                    # Render clarifier UI
                    return self._render_clarifier_response(ai_result, user_hash, rid)
                    
            elif decision == "RAW_ONLY":
                # Low confidence - save raw with minimal categorization
                if amount and amount > 0:
                    success = self._save_cc_expense_with_overlays(user_hash, amount, "other", note or "Raw expense", merchant_text, text, rid)
                    if success:
                        return f"✅ Saved ৳{amount:.0f} (will categorize later)", "log_single", "other", amount
                    else:
                        return "Failed to save expense, please try again.", "error", None, None
                else:
                    return ui_note or "I see an expense but need a clear amount.", "help", None, None
            
            else:
                # Unknown decision or HELP intent
                return ui_note or "I'm here to help! Try something like 'coffee 50' to log expenses.", "help", None, None
                
        except Exception as e:
            logger.error(f"ON mode handling failed: {e}")
            return "Processing failed, please try again.", "error", None, None
    
    def _save_cc_expense_raw_only(self, user_hash: str, amount: float, category: str, note: str, 
                                merchant_text: str, original_text: str, rid: str) -> bool:
        """Save expense to RAW ledger only (DRYRUN mode)"""
        try:
            from utils.db import save_expense
            
            # Create description from available data
            description_parts = []
            if merchant_text:
                description_parts.append(merchant_text)
            if note and note != merchant_text:
                description_parts.append(note)
            if not description_parts:
                description_parts.append(f"{category or 'expense'}")
            
            description = " - ".join(description_parts)
            
            # Save to RAW ledger only (no overlay tables in DRYRUN)
            save_expense(
                user_identifier=user_hash,
                description=description,
                amount=amount,
                category=category or "other",
                platform="facebook",
                original_message=original_text,
                unique_id=rid
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save RAW-only CC expense: {e}")
            return False
    
    def _save_cc_expense_with_overlays(self, user_hash: str, amount: float, category: str, note: str,
                                     merchant_text: str, original_text: str, rid: str) -> bool:
        """Save expense to RAW + overlay tables (ON mode)"""
        try:
            from utils.db import save_expense
            
            # Create description from available data
            description_parts = []
            if merchant_text:
                description_parts.append(merchant_text)
            if note and note != merchant_text:
                description_parts.append(note)
            if not description_parts:
                description_parts.append(f"{category or 'expense'}")
            
            description = " - ".join(description_parts)
            
            # Save to RAW + overlay tables
            save_expense(
                user_identifier=user_hash,
                description=description,
                amount=amount,
                category=category or "other",
                platform="facebook",
                original_message=original_text,
                unique_id=rid
            )
            
            # TODO: Add overlay table writes here when overlay system is implemented
            # This would include category corrections, audit trails, etc.
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save CC expense with overlays: {e}")
            return False
    
    def _format_full_audit_response(self, amount: float, category: str, ui_note: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Format response for ON mode with full audit transparency"""
        if ui_note:
            # Use AI-generated response
            response = ui_note
        else:
            # Default format with audit info
            response = f"✅ Logged ৳{amount:.0f} for {category or 'expense'}"
        
        # TODO: Add audit transparency info when overlay system is ready
        # response += "\n🔍 View details: /audit/{tx_id}"
        
        return response, "log_single", category, amount
    
    def _render_clarifier_response(self, cc_data: Dict[str, Any], user_hash: str, rid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Render clarifier UI (Phase 3+) - placeholder for now"""
        # Phase 2: clarifiers disabled, should not reach here
        # Phase 3+: will implement clarifier chip rendering
        ui_note = cc_data.get('ui_note', 'Saved expense, please confirm category.')
        slots = cc_data.get('slots', {})
        return ui_note, "clarification_needed", slots.get('category'), slots.get('amount')
    
    def _route_ai_conversation(self, text: str, psid: str, psid_hash: str, rid: str, rate_limit_result) -> Tuple[str, str, Optional[str], Optional[float]]:
        """Route to AI for natural conversation (NOT expense parsing)"""
        self._log_routing_decision(rid, psid_hash, "ai_conversation", "natural_chat_attempt")
        
        try:
            # Use AI adapter for natural conversation
            from utils.ai_adapter_v2 import production_ai_adapter
            ai = production_ai_adapter
            
            # Get user context for personalized conversation
            try:
                from utils.conversational_ai import ConversationalAI
                conv_ai = ConversationalAI()
                
                # Generate context-aware response
                response = conv_ai.generate_conversational_response(psid_hash, text)
                mode = "CONVERSATION"
                
            except Exception as conv_error:
                logger.warning(f"Conversational AI failed: {conv_error}")
                
                # Simple AI fallback without expense parsing
                try:
                    # Direct AI call for general conversation
                    prompt = f"""You are FinBrain, a friendly AI financial assistant. A user said: "{text}"

Respond naturally and helpfully. If they're asking about expenses, guide them to say something like "coffee 50" or "spent 200 on groceries". Keep it under 280 characters and friendly.

Do NOT try to parse this as an expense. Just have a natural conversation."""
                    
                    response = ai.get_completion(prompt)
                    mode = "AI_SIMPLE"
                    
                except Exception as ai_error:
                    logger.warning(f"Simple AI conversation failed: {ai_error}")
                    # Final fallback
                    response = "I'm here to help with your expenses! You can log expenses like 'coffee 50' or ask 'summary' to see your spending."
                    mode = "FALLBACK"
            
            # Clean and normalize response
            response = normalize(response)
            if len(response) > 280:
                response = response[:277] + "..."
            
            self._log_routing_decision(rid, psid_hash, "ai_conversation", f"chat_success_{mode}")
            return response, "conversation", None, None
            
        except Exception as e:
            logger.error(f"AI conversation routing failed: {e}")
            response = "I'm here to help! Try logging an expense like 'coffee 50' or ask for your 'summary'."
            self._log_routing_decision(rid, psid_hash, "ai_conversation", f"chat_error: {str(e)}")
            return normalize(response), "conversation_error", None, None
    
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
        
        # Generate AI-powered response with intelligent tips and audit transparency
        tx_id = f"{psid_hash[:8]}-{int(time.time())}"  # Generate transaction ID
        response = self._generate_ai_logged_response(amount, note, category, ai_result.get('tips', []), tx_id, psid)
        
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
            
            # CONSENT VALIDATION: Check if user has given privacy consent before allowing data collection
            user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
            if user and not user.privacy_consent_given:
                # Check if user is giving consent now
                if self._detect_user_consent(text):
                    # User is giving consent - update database
                    from datetime import datetime
                    user.privacy_consent_given = True
                    user.privacy_consent_at = datetime.utcnow()
                    user.terms_accepted = True
                    user.terms_accepted_at = datetime.utcnow()
                    db.session.commit()
                    
                    return "✅ Thank you! Your privacy preferences have been saved. You can now continue using finbrain to track your expenses.", "consent_accepted", None, None
                else:
                    # User hasn't given consent - redirect to privacy consent
                    consent_message = (
                        "🔒 To continue using finbrain, please review and accept:\n\n"
                        "📋 Privacy Policy: https://www.finbrain.app/privacy-policy\n"
                        "📜 Terms of Service: https://www.finbrain.app/terms-of-service\n\n"
                        "Reply \"I agree\" to continue tracking your expenses."
                    )
                    return consent_message, "consent_required", None, None
            
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
    
    def _detect_user_consent(self, user_text: str) -> bool:
        """Detect if user has given consent (same logic as onboarding)"""
        consent_patterns = [
            "i agree", "i accept", "yes", "okay", "ok", "sure", 
            "agreed", "accept", "consent", "i consent", "yes i agree"
        ]
        text_lower = user_text.lower().strip()
        return any(pattern in text_lower for pattern in consent_patterns)
    
    def _detect_problem_report(self, text: str) -> bool:
        """Detect if user is reporting a problem"""
        text_lower = text.lower().strip()
        
        # Check for explicit problem report payload
        if text == "REPORT_PROBLEM":
            return True
        
        # Check for natural language problem reporting
        problem_phrases = [
            "report a problem", "there's a problem", "something's wrong", "not working",
            "broken", "error", "bug", "issue", "problem with", "having trouble",
            "can't log", "won't work", "doesn't work", "app is", "finbrain is"
        ]
        
        return any(phrase in text_lower for phrase in problem_phrases)
    
    def _handle_problem_report(self, user_hash: str, text: str) -> str:
        """Handle user problem report and create ticket"""
        try:
            from utils.problem_reporter import report_problem, get_problem_report_response
            
            # Determine what the user was trying to do (context)
            last_action = "unknown"
            if "log" in text.lower() or "expense" in text.lower():
                last_action = "logging_expense"
            elif "summary" in text.lower() or "balance" in text.lower():
                last_action = "viewing_summary"
            elif "slow" in text.lower() or "loading" in text.lower():
                last_action = "waiting_for_response"
            
            # Create ticket
            ticket_id = report_problem(user_hash, text, last_action)
            
            # Get user-friendly response
            response = get_problem_report_response(ticket_id)
            
            # Add quick replies for follow-up support
            from utils.quick_reply_system import send_custom_quick_replies
            support_replies = [
                {"title": "Get help", "payload": "HELP"},
                {"title": "Try again", "payload": "TRY_AGAIN"},
                {"title": "FAQ", "payload": "FAQ"}
            ]
            
            # Note: We'll return the response and the quick replies will be handled by the caller
            return response
            
        except Exception as e:
            logger.error(f"Problem report handling failed: {e}")
            return "Thanks for letting us know about the issue. We'll look into it and work on improvements."

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
    
    def _generate_ai_logged_response(self, amount: float, note: str, category: str, tips: List[str], tx_id: str = None, psid: str = None) -> str:
        """Generate AI-powered response for logged expenses with audit transparency"""
        
        # Base confirmation with amount and note
        response = f"Logged: ৳{amount:.2f}"
        
        # Add note if present
        if note.strip():
            response += f" — {note}"
        
        # Add category insight
        if category != 'other':
            response += f" ({category})"
        
        # Check if audit transparency should be shown
        audit_info = self._get_audit_transparency_info(tx_id, psid, amount, category, note)
        if audit_info:
            response += f"\n{audit_info}"
        else:
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
    
    def _get_audit_transparency_info(self, tx_id: str, psid: str, amount: float, category: str, note: str) -> Optional[str]:
        """Get audit transparency information for a transaction if enabled"""
        
        # Check if audit UI is enabled
        if not _is_audit_ui_enabled():
            return None
        
        try:
            # Import audit API functions
            import requests
            from utils.identity import psid_hash
            
            # Get user hash
            user_hash = psid_hash(psid) if psid else 'anonymous'
            
            # Call audit API for compact format
            response = requests.get(
                f"http://localhost:5000/api/audit/transactions/{tx_id}/compare?user_id={user_hash}",
                timeout=2  # Quick timeout for real-time responses
            )
            
            if response.status_code == 200:
                data = response.json()
                chat_format = data.get('chat_format', '')
                
                # Ensure it fits in messenger format
                if len(chat_format) <= 200:  # Leave room for rest of message
                    return chat_format
                else:
                    # Fallback: show basic audit info
                    return f"View details: /user/{user_hash[:8]}/insights"
            
        except Exception as e:
            # Silent failure - don't break the main flow
            logger.debug(f"Audit transparency failed: {e}")
            
        return None
    
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
            
            # Generate success response with audit transparency
            currency_symbol = '৳' if currency == 'BDT' else '$' if currency == 'USD' else '€' if currency == 'EUR' else '£' if currency == 'GBP' else '₹'
            response = f"✅ Logged: {currency_symbol}{amount:.0f} for {category}"
            
            # Add audit transparency if enabled
            audit_info = self._get_audit_transparency_info(rid, psid, float(amount), category, note)
            if audit_info:
                response += f"\n{audit_info}"
            
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

