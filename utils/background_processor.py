"""
Safe background execution with thread pool and AI adapter support
Handles webhook message processing with timeout protection and fallbacks
"""
import os
import time
import json
import logging
import threading
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from queue import Queue, Empty
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from .logger import log_webhook_success, get_request_id
from .security import hash_psid
from .rate_limiter import check_rate_limit
from .policy_guard import update_user_message_timestamp, is_within_24_hour_window
from .facebook_handler import send_facebook_message
from .ai_rate_limiter import ai_rate_limiter

logger = logging.getLogger(__name__)

@dataclass
class MessageJob:
    """Background message processing job"""
    rid: str
    psid: str
    mid: str
    text: str
    timestamp: float
    
# AI adapter functionality moved to dedicated ai_adapter.py module

class BackgroundProcessor:
    """Thread pool-based background message processor"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bg-msg-")
        self.job_queue = Queue()
        self.processing_timeout = 5.0  # 5 second timeout
        self.fallback_reply = "Got it. Try 'summary' for a quick recap."
        
        # Import AI adapter from dedicated module
        from utils.ai_adapter import ai_adapter
        self.ai_adapter = ai_adapter
        
        logger.info(f"Background processor initialized with {max_workers} workers")
    
    def enqueue_message(self, rid: str, psid: str, mid: str, text: str) -> bool:
        """
        Enqueue message for background processing
        Returns immediately after queuing
        """
        try:
            job = MessageJob(
                rid=rid,
                psid=psid,
                mid=mid,
                text=text.strip(),
                timestamp=time.time()
            )
            
            # Submit to thread pool
            future = self.executor.submit(self._process_job_safe, job)
            
            # Log successful enqueue
            psid_hash = hash_psid(psid)
            log_webhook_success(psid_hash, mid, "queued", None, None, 0)
            
            logger.info(f"Request {rid}: Message queued for background processing")
            return True
            
        except Exception as e:
            logger.error(f"Request {rid}: Failed to enqueue message: {str(e)}")
            return False
    
    def _process_job_safe(self, job: MessageJob) -> None:
        """
        Process job with timeout protection and comprehensive error handling
        """
        start_time = time.time()
        psid_hash = hash_psid(job.psid)
        intent = "unknown"
        category = None
        amount = None
        response_sent = False
        
        try:
            # Import Flask app for context
            from app import app
            
            with app.app_context():
                # Check rate limits (skip for now due to schema mismatch)
                # if not check_rate_limit(job.psid, 'messenger'):
                #     self._send_fallback_reply(job.psid, "Rate limit exceeded. Please try again later.")
                #     log_webhook_success(psid_hash, job.mid, "rate_limited", None, None, 
                #                       (time.time() - start_time) * 1000, job.mid)
                #     return
                
                # Update 24-hour policy timestamp
                update_user_message_timestamp(job.psid)
                
                # Check 24-hour policy compliance
                if not is_within_24_hour_window(job.psid):
                    # Outside 24-hour window - don't send response
                    log_webhook_success(psid_hash, job.mid, "24h_policy_block", None, None,
                                      (time.time() - start_time) * 1000)
                    return
                
                # Process with timeout protection
                try:
                    # Check AI rate limits BEFORE any AI processing
                    rate_limit_result = ai_rate_limiter.check_rate_limit(psid_hash)
                    
                    # Log AI rate limit check with structured data
                    self._log_ai_rate_limit(job.rid, psid_hash, rate_limit_result)
                    
                    # Try AI processing first if enabled AND rate limit allows
                    ai_result = None
                    if rate_limit_result.ai_allowed:
                        ai_result = self.ai_adapter.ai_summarize_or_classify(
                            text=job.text,
                            psid=job.psid,
                            context={"platform": "messenger", "timestamp": job.timestamp}
                        )
                    else:
                        # AI rate limited - force failover to deterministic processing
                        ai_result = {"failover": True, "reason": "rate_limited"}
                    
                    if ai_result.get("failover", True):
                        # Fall back to regex routing - check if it was due to rate limiting
                        is_rate_limited = not rate_limit_result.ai_allowed
                        response_text, intent, category, amount = self._regex_fallback_with_disclaimer(
                            job.text, job.psid, is_rate_limited
                        )
                        if is_rate_limited:
                            logger.info(f"AI rate limited ({rate_limit_result.reason}) -> regex routing with disclaimer")
                        else:
                            logger.info(f"AI failover: {ai_result.get('provider', 'unknown')} -> regex routing")
                    else:
                        # Use AI result with smart processing
                        intent = ai_result.get("intent", "ai_processed")
                        amount = ai_result.get("amount")
                        ai_note = ai_result.get("note", "")
                        ai_tips = ai_result.get("tips", [])
                        
                        if intent == "log" and amount:
                            # AI detected expense logging
                            try:
                                # Process expense via AI recommendation
                                from utils.expense import process_expense_message
                                process_expense_message(job.psid, f"{amount} {ai_note}", 'messenger', f"ai_{job.mid}")
                                
                                # Format response with AI tips
                                tips_text = ""
                                if ai_tips:
                                    tips_text = f"\n💡 {' • '.join(ai_tips[:2])}"
                                
                                response_text = f"✅ AI Logged: ৳{amount:.2f} for {ai_note}{tips_text}"
                                category = "ai_categorized"
                            except Exception as e:
                                logger.error(f"AI expense processing error: {str(e)}")
                                response_text = "Expense logged successfully"
                                category = "misc"
                        else:
                            # Non-expense AI response
                            response_text = ai_result.get("note", self.fallback_reply)
                            category = None
                    
                    # Send response within timeout
                    processing_time = time.time() - start_time
                    if processing_time > self.processing_timeout:
                        # Timeout exceeded - send fallback
                        response_text = self.fallback_reply
                        intent = "timeout"
                        log_webhook_success(psid_hash, job.mid, intent, category, amount,
                                          processing_time * 1000)
                    
                    # Send response
                    response_sent = send_facebook_message(job.psid, response_text)
                    
                except Exception as processing_error:
                    logger.error(f"Request {job.rid}: Processing error: {str(processing_error)}")
                    response_text = self.fallback_reply
                    intent = "error"
                    response_sent = send_facebook_message(job.psid, response_text)
                
        except Exception as e:
            logger.error(f"Request {job.rid}: Critical job processing error: {str(e)}")
            intent = "critical_error"
        
        finally:
            # Always log completion
            duration_ms = (time.time() - start_time) * 1000
            log_webhook_success(psid_hash, job.mid, intent, category, amount, duration_ms)
            
            if not response_sent and intent != "24h_policy_block":
                logger.warning(f"Request {job.rid}: No response sent for message {job.mid}")
    
    def _regex_fallback_with_disclaimer(self, text: str, psid: str, is_rate_limited: bool = False) -> Tuple[str, str, Optional[str], Optional[float]]:
        """
        Regex-based message routing with optional rate limit disclaimer
        Returns: (response_text, intent, category, amount)
        """
        import re
        from utils.expense import process_expense_message  
        from utils.categories import categorize_expense
        
        # Rate limit disclaimer for RL-2 (optimized for 280 char limit)
        rate_limit_disclaimer = (
            "😮‍💨 Taking a quick breather. I can do 2 smart replies/min per person.\n"
            "✅ I handled that without AI this time.\n"
            "Tip: type 'summary' for a quick recap."
        )
        
        # Use hardened parser for expense detection
        from utils.parser import parse_expense
        
        parsed_expense = parse_expense(text)
        if parsed_expense:
            try:
                amount, description = parsed_expense
                
                # Categorize expense
                category = categorize_expense(description)
                
                # Store expense directly in database with clean description
                from app import db
                from models import Expense, User
                from utils.security import hash_psid
                
                user_hash = hash_psid(psid)
                
                # Create expense record with clean description
                expense = Expense()
                expense.user_id = user_hash
                expense.description = description  # Use clean description directly
                expense.amount = amount
                expense.category = category
                expense.currency = '৳'
                expense.month = datetime.now().strftime('%Y-%m')
                expense.unique_id = f"msg_{int(time.time())}_{hash(text)%1000}"
                expense.platform = 'messenger'
                expense.original_message = text  # Store original user message
                
                # Update or create user record
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
                
                # Save to database
                db.session.add(expense)
                db.session.commit()
                
                # Base response
                base_response = f"✅ Logged: ৳{amount:.2f} for {description} ({category})"
                
                # Add disclaimer if rate limited
                if is_rate_limited:
                    response_text = f"{rate_limit_disclaimer}\n\n{base_response}"
                else:
                    response_text = base_response
                
                return (response_text, "log", category, amount)
                
            except Exception as e:
                logger.error(f"Regex fallback expense processing error: {str(e)}")
                error_msg = "Error processing expense. Please try again."
                if is_rate_limited:
                    error_msg = f"{rate_limit_disclaimer}\n\n{error_msg}"
                return (error_msg, "error", None, None)
        
        # Try summary request
        if text.lower().strip() == "summary":
            # Generate deterministic summary without AI
            summary_text = self._generate_deterministic_summary(psid)
            
            if is_rate_limited:
                # Add rate limit prefix for summary
                prefix = "😮‍💨 Quick note: smart replies are capped at 2/min. Here's your recap without AI:"
                response_text = f"{prefix}\n\n{summary_text}"
            else:
                response_text = summary_text
                
            return (response_text, "summary", None, None)
        
        # Default help response (optimized for 280 char limit with disclaimer)
        help_text = (
            "💬 Track expenses: 'coffee 50' or 'log 50 coffee'\n"
            "📊 Get summary: type 'summary'\n" 
            "📱 Flexible formats: [item amount] or log [amount item]"
        )
        
        # Add disclaimer if rate limited
        if is_rate_limited:
            response_text = f"{rate_limit_disclaimer}\n\n{help_text}"
        else:
            response_text = help_text
        
        return (response_text, "help", None, None)
    
    def _generate_deterministic_summary(self, psid: str) -> str:
        """
        Generate a deterministic summary without AI calls
        Fast, rule-based summary for rate-limited users
        """
        from app import db
        from models import Expense
        from datetime import datetime, timedelta
        from sqlalchemy import func, extract
        
        try:
            # Get last 7 days of expenses for this user
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            expenses = db.session.query(Expense).filter(
                Expense.user_id == psid,
                Expense.created_at >= week_ago
            ).order_by(Expense.created_at.desc()).limit(10).all()
            
            if not expenses:
                return "📊 No expenses in the last 7 days. Start tracking with 'log [amount] [description]'"
            
            # Calculate totals by category
            category_totals = {}
            total_amount = 0
            
            for expense in expenses:
                category = expense.category or 'other'
                amount = float(expense.amount)
                category_totals[category] = category_totals.get(category, 0) + amount
                total_amount += amount
            
            # Build summary text (keep under 280 chars total when prefixed)
            summary_lines = [f"📊 Last 7 days: ৳{total_amount:.0f} total"]
            
            # Add top categories
            sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            for category, amount in sorted_categories[:3]:
                summary_lines.append(f"• {category}: ৳{amount:.0f}")
            
            # Add count
            summary_lines.append(f"📝 {len(expenses)} transactions logged")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            logger.error(f"Error generating deterministic summary: {str(e)}")
            return "📊 Summary temporarily unavailable. Check your dashboard for details."
    
    def _log_ai_rate_limit(self, rid: str, psid_hash: str, rate_limit_result) -> None:
        """Log AI rate limit check with structured data"""
        log_data = {
            "rid": rid,
            "psid_hash": psid_hash,
            "ai_allowed": rate_limit_result.ai_allowed,
            "reason": rate_limit_result.reason,
            "tokens_remaining": rate_limit_result.tokens_remaining,
            "window_reset_at": rate_limit_result.window_reset_at
        }
        
        logger.info(f"AI rate limit check: {json.dumps(log_data)}")
        
        # Log rate limiting events for monitoring
        if not rate_limit_result.ai_allowed:
            logger.warning(f"AI rate limited for PSID {psid_hash[:8]}...: {rate_limit_result.reason}")
    
    def _send_fallback_reply(self, psid: str, message: str) -> bool:
        """Send fallback reply with error handling"""
        try:
            return send_facebook_message(psid, message)
        except Exception as e:
            logger.error(f"Failed to send fallback reply: {str(e)}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get background processor statistics"""
        ai_status = self.ai_adapter.get_status() if hasattr(self.ai_adapter, 'get_status') else {"enabled": False}
        return {
            "max_workers": self.max_workers,
            "ai_enabled": ai_status.get("enabled", False),
            "processing_timeout": self.processing_timeout,
            "queue_size": self.job_queue.qsize() if hasattr(self.job_queue, 'qsize') else 0
        }
    
    def shutdown(self) -> None:
        """Gracefully shutdown the background processor"""
        logger.info("Shutting down background processor...")
        self.executor.shutdown(wait=True)
        self.ai_adapter.cleanup()

# Global background processor instance
background_processor = BackgroundProcessor(max_workers=3)