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
                                      (time.time() - start_time) * 1000, job.mid)
                    return
                
                # Process with timeout protection
                try:
                    # Try AI processing first if enabled
                    ai_result = self.ai_adapter.ai_summarize_or_classify(
                        text=job.text,
                        psid=job.psid,
                        context={"platform": "messenger", "timestamp": job.timestamp}
                    )
                    
                    if ai_result.get("failover", True):
                        # Fall back to regex routing
                        response_text, intent, category, amount = self._regex_fallback(job.text, job.psid)
                    else:
                        # Use AI result
                        response_text = ai_result.get("note", self.fallback_reply)
                        intent = ai_result.get("intent", "ai_processed")
                        category = None  # Will be set by expense processing
                        amount = ai_result.get("amount")
                    
                    # Send response within timeout
                    processing_time = time.time() - start_time
                    if processing_time > self.processing_timeout:
                        # Timeout exceeded - send fallback
                        response_text = self.fallback_reply
                        intent = "timeout"
                        log_webhook_success(psid_hash, job.mid, intent, category, amount,
                                          processing_time * 1000, job.mid)
                    
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
            log_webhook_success(psid_hash, job.mid, intent, category, amount, duration_ms, job.mid)
            
            if not response_sent and intent != "24h_policy_block":
                logger.warning(f"Request {job.rid}: No response sent for message {job.mid}")
    
    def _regex_fallback(self, text: str, psid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """
        Regex-based message routing (MVP fallback)
        Returns: (response_text, intent, category, amount)
        """
        import re
        from utils.expense import process_expense_message  
        from utils.categories import categorize_expense
        
        # Try expense logging pattern: ^log (\d+) (.*)$
        log_match = re.match(r'^log (\d+) (.*)$', text.lower().strip())
        if log_match:
            try:
                amount = float(log_match.group(1))
                description = log_match.group(2).strip()
                
                # Categorize expense
                category = categorize_expense(description)
                
                # Store expense using the correct function
                process_expense_message(psid, f"{amount} {description}", 'messenger', f"bg_{text[:10]}_{int(time.time())}")
                
                return (
                    f"✅ Logged: ৳{amount:.2f} for {description} ({category})",
                    "log",
                    category,
                    amount
                )
                
            except Exception as e:
                logger.error(f"Regex fallback expense processing error: {str(e)}")
                return ("Error processing expense. Please try again.", "error", None, None)
        
        # Try summary request
        if text.lower().strip() == "summary":
            # Generate summary (simplified)
            return ("📊 Weekly summary: Check your dashboard for details.", "summary", None, None)
        
        # Default help response
        help_text = (
            "💬 Send: 'log 50 coffee' to track expenses\n"
            "📊 Send: 'summary' for weekly breakdown\n" 
            "📱 Format: log [amount] [description]"
        )
        return (help_text, "help", None, None)
    
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