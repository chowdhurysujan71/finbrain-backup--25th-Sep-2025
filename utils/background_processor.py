"""
Safe background execution with thread pool and AI adapter support
Includes RL-2 graceful non-AI fallback system
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
from .user_manager import resolve_user_id
from .identity import psid_hash
from .rate_limiter import check_rate_limit
from .policy_guard import update_user_message_timestamp, is_within_24_hour_window
from .facebook_handler import send_facebook_message
from .ai_rate_limiter import ai_rate_limiter
from .background_processor_rl2 import rl2_processor
from utils.production_router import production_router

logger = logging.getLogger(__name__)

@dataclass
class MessageJob:
    """Background message processing job"""
    rid: str
    psid: str
    mid: str
    text: str
    timestamp: float

class BackgroundProcessor:
    """Thread pool-based background message processor with RL-2 support"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bg-msg-")
        self.job_queue = Queue()
        self.processing_timeout = 5.0
        self.fallback_reply = "Got it. I'll track that for you."
        
        # Import AI adapter from dedicated module
        from utils.ai_adapter_v2 import production_ai_adapter as ai_adapter
        self.ai_adapter = ai_adapter
        
        # Initialize reminder system
        self._last_reminder_check = datetime.utcnow()
        self._reminder_check_interval = 300  # 5 minutes
        
        # Context-driven processing now handled by production router
        
        logger.info(f"Background processor initialized with {max_workers} workers")
    
    def enqueue_message(self, rid: str, psid: str, mid: str, text: str) -> bool:
        """Enqueue message for background processing"""
        try:
            job = MessageJob(
                rid=rid,
                psid=psid,
                mid=mid,
                text=text.strip(),
                timestamp=time.time()
            )
            
            future = self.executor.submit(self._process_job_safe, job)
            
            psid_hash = resolve_user_id(psid=psid)
            log_webhook_success(psid_hash, mid, "queued", None, None, 0)
            
            logger.info(f"Request {rid}: Message queued for background processing")
            return True
            
        except Exception as e:
            logger.error(f"Request {rid}: Failed to enqueue message: {str(e)}")
            return False
    
    def _process_job_safe(self, job: MessageJob) -> None:
        """Process job with timeout protection and RL-2 support"""
        start_time = time.time()
        psid_hash = resolve_user_id(psid=job.psid)
        intent = "unknown"
        category = None
        amount = None
        response_sent = False
        
        try:
            from app import app
            
            with app.app_context():
                # Check for pending reminders periodically
                self._check_reminders_if_due()
                
                # Update 24-hour policy timestamp
                update_user_message_timestamp(job.psid)
                
                # Check 24-hour policy compliance
                if not is_within_24_hour_window(job.psid):
                    log_webhook_success(psid_hash, job.mid, "24h_policy_block", None, None,
                                      (time.time() - start_time) * 1000)
                    return
                
                try:
                    # Use production router for all message processing
                    response_text, intent, category, amount = production_router.route_message(
                        job.text, job.psid, job.rid
                    )
                    
                    # Send response within timeout
                    processing_time = time.time() - start_time
                    if processing_time > self.processing_timeout:
                        response_text = self.fallback_reply
                        intent = "timeout"
                        log_webhook_success(psid_hash, job.mid, intent, category, amount,
                                          processing_time * 1000)
                    
                    # Send response with clear error handling + debug echo for 24h
                    try:
                        # Always use AI templates - no debug footers
                        from templates.replies_ai import clean_ai_reply
                        clean_response = clean_ai_reply(response_text)
                        response_sent = send_facebook_message(job.psid, clean_response)
                        logger.info(f"Request {job.rid}: Response sent successfully to {job.psid[:10]}*** (hash: {psid_hash[:8]}...)")
                    except ValueError as psid_error:
                        # Invalid PSID - clear error, no fallback attempt
                        logger.error(f"Request {job.rid}: PSID validation failed - {str(psid_error)}")
                        response_sent = False
                    except RuntimeError as api_error:
                        # Facebook API error - clear error, try simple fallback
                        logger.error(f"Request {job.rid}: Facebook API error - {str(api_error)}")
                        try:
                            # Clean AI fallback response
                            response_sent = send_facebook_message(job.psid, "Got it! ✅")
                            logger.info(f"Request {job.rid}: Fallback message sent successfully (hash: {psid_hash[:8]}...)")
                        except Exception as fallback_error:
                            logger.error(f"Request {job.rid}: Fallback send failed - {str(fallback_error)}")
                            response_sent = False
                    except Exception as unknown_error:
                        # Unexpected error - log with full context
                        logger.error(f"Request {job.rid}: Unexpected messaging error - {str(unknown_error)}")
                        response_sent = False
                    
                except Exception as processing_error:
                    logger.error(f"Request {job.rid}: Processing error: {str(processing_error)}")
                    response_text = self.fallback_reply
                    intent = "error"
                    # Always attempt response even on processing errors
                    try:
                        # Clean AI error response
                        from templates.replies_ai import format_ai_error_reply, clean_ai_reply
                        clean_error = format_ai_error_reply("general")
                        response_sent = send_facebook_message(job.psid, clean_error)
                        logger.info(f"Request {job.rid}: Error response sent successfully (hash: {psid_hash[:8]}...)")
                    except ValueError as psid_error:
                        logger.error(f"Request {job.rid}: Error response failed - invalid PSID: {str(psid_error)}")
                        response_sent = False
                    except Exception as send_error:
                        logger.error(f"Request {job.rid}: Error response send failed: {str(send_error)}")
                        response_sent = False
                
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
        Regex-based message routing (non-rate-limited fallback)
        For rate-limited scenarios, use RL-2 processor instead
        """
        from utils.parser import parse_expense
        from utils.expense import process_expense_message
        from utils.categories import categorize_expense
        
        # Use streamlined parser for expense detection
        parsed_expense = parse_expense(text)
        if parsed_expense:
            try:
                amount, description = parsed_expense
                category = categorize_expense(description)
                
                # Process expense using existing system
                process_expense_message(psid, text, 'messenger', f"regex_{int(time.time())}")
                
                response = f"✅ Logged: ৳{amount:.2f} for {description} ({category.title()})"
                return response, "log", category, amount
                
            except Exception as e:
                logger.error(f"Regex fallback expense processing error: {str(e)}")
                return "Error processing expense. Please try again.", "error", None, None
        
        # Try summary request
        if text.lower().strip() == "summary":
            summary_text = self._generate_simple_summary(psid)
            return summary_text, "summary", None, None
        
        # Default help response
        help_text = (
            "💬 Track expenses: 'coffee 50' or 'log 50 coffee'\n"
            "📊 Get summary: type 'summary'\n" 
            "📱 Flexible formats: [item amount] or log [amount item]"
        )
        
        return help_text, "help", None, None
    
    def _generate_simple_summary(self, psid: str) -> str:
        """Generate a simple summary without AI calls"""
        from app import db
        from models import Expense
        from datetime import datetime, timedelta
        
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)
            user_hash = psid_hash(psid)
            
            expenses = db.session.query(Expense).filter(
                Expense.user_id == user_hash,
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
            
            # Build summary text
            summary_lines = [f"📊 Last 7 days: ৳{total_amount:.0f} total"]
            
            # Add top categories
            sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            for category, amount in sorted_categories[:3]:
                summary_lines.append(f"• {category}: ৳{amount:.0f}")
            
            summary_lines.append(f"📝 {len(expenses)} transactions logged")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
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
        
        if not rate_limit_result.ai_allowed:
            logger.warning(f"AI rate limited for PSID {psid_hash[:8]}...: {rate_limit_result.reason}")
    
    def _send_fallback_reply(self, psid: str, message: str) -> bool:
        """Send fallback reply message"""
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
    
    def _check_reminders_if_due(self) -> None:
        """Check and send reminders if enough time has passed since last check"""
        now = datetime.utcnow()
        time_since_last_check = (now - self._last_reminder_check).total_seconds()
        
        if time_since_last_check >= self._reminder_check_interval:
            # DISABLED: No outbound messaging for policy compliance
            # Only respond to inbound messages - no proactive reminders
            logger.debug("Reminder system disabled for policy compliance")
            self._last_reminder_check = now

    def shutdown(self) -> None:
        """Gracefully shutdown the background processor"""
        logger.info("Shutting down background processor...")
        self.executor.shutdown(wait=True)
        if hasattr(self.ai_adapter, 'cleanup'):
            self.ai_adapter.cleanup()

# Create background processor instance
background_processor = BackgroundProcessor()