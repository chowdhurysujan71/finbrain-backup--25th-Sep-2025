"""Fast Messenger webhook processing with signature verification and async handling"""
import hashlib
import hmac
import json
import logging
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from .logger import log_webhook_success, get_request_id

logger = logging.getLogger(__name__)

# Thread pool for async processing (max 10 concurrent tasks)
executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="webhook-")

# Message deduplication cache (simple in-memory for MVP)
processed_messages = {}
cache_cleanup_interval = 3600  # 1 hour
last_cleanup = time.time()

def verify_webhook_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """Verify Facebook webhook signature"""
    try:
        if not signature or not signature.startswith('sha256='):
            return False
        
        expected_signature = hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        received_signature = signature[7:]  # Remove 'sha256=' prefix
        return hmac.compare_digest(expected_signature, received_signature)
        
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False

def is_duplicate_message(message_id: str) -> bool:
    """Check if message has already been processed"""
    global processed_messages, last_cleanup
    
    # Cleanup old entries periodically
    current_time = time.time()
    if current_time - last_cleanup > cache_cleanup_interval:
        cleanup_old_messages()
        last_cleanup = current_time
    
    if message_id in processed_messages:
        return True
    
    # Mark as processed
    processed_messages[message_id] = current_time
    return False

def cleanup_old_messages():
    """Remove processed messages older than 1 hour"""
    cutoff_time = time.time() - cache_cleanup_interval
    to_remove = [mid for mid, timestamp in processed_messages.items() if timestamp < cutoff_time]
    for mid in to_remove:
        del processed_messages[mid]
    logger.debug(f"Cleaned up {len(to_remove)} old message entries")

def extract_webhook_events(data: Dict[str, Any]) -> list:
    """Extract and validate webhook events from payload"""
    events = []
    
    if not data or data.get('object') != 'page':
        return events
    
    for entry in data.get('entry', []):
        for messaging in entry.get('messaging', []):
            # Filter out non-message events (delivery, read, typing)
            if messaging.get('delivery') or messaging.get('read'):
                logger.debug(f"Skipping non-message event: delivery={bool(messaging.get('delivery'))}, read={bool(messaging.get('read'))}")
                continue
            
            # Extract basic event data
            sender_id = messaging.get('sender', {}).get('id')
            message = messaging.get('message', {})
            message_text = message.get('text', '')
            message_id = message.get('mid', '')
            
            if sender_id and message_text and message_id:
                events.append({
                    'psid': sender_id,
                    'text': message_text,
                    'mid': message_id,
                    'timestamp': messaging.get('timestamp', int(time.time() * 1000))
                })
    
    return events

def process_message_async(event: Dict[str, Any], request_id: str):
    """Process message asynchronously with timeout and MVP routing"""
    start_time = time.time()
    psid = event['psid']
    mid = event['mid']
    text = event['text']
    outcome = "success"
    intent = "unknown"
    
    try:
        # Import lightweight routing and rate limiting
        from utils.rate_limiter import check_rate_limit
        from utils.mvp_router import route_message
        from utils.facebook_handler import send_facebook_message
        from utils.security import hash_psid
        
        # Check rate limits first
        if not check_rate_limit(psid, 'messenger'):
            outcome = "rate_limited"
            duration_ms = (time.time() - start_time) * 1000
            psid_hash = hash_psid(psid)
            log_webhook_success(psid_hash, mid, "rate_limited", None, None, duration_ms)
            return
        
        # Update 24-hour policy timestamp first
        from utils.policy_guard import update_user_message_timestamp, is_within_24_hour_window
        update_user_message_timestamp(psid)
        
        # Check 24-hour policy compliance before responding
        if not is_within_24_hour_window(psid):
            # Outside 24-hour window - don't send response
            outcome = "24h_policy_block"
            duration_ms = (time.time() - start_time) * 1000
            psid_hash = hash_psid(psid)
            log_webhook_success(psid_hash, mid, "blocked", None, None, duration_ms)
            return
        
        # Route message using MVP regex patterns
        response_text, intent = route_message(psid, text)
        
        # Send response back to user (within 24-hour window)
        response_sent = send_facebook_message(psid, response_text)
        
        if not response_sent:
            outcome = "send_failed"
            logger.warning(f"Failed to send response for mid={mid}")
        
    except Exception as e:
        outcome = f"error:{str(e)[:30]}"
        logger.error(f"Async processing error for mid={mid}: {str(e)}")
    
    finally:
        duration_ms = (time.time() - start_time) * 1000
        psid_hash = hash_psid(psid)
        # Extract category and amount if successful expense log
        category = None
        amount = None
        if outcome == "success" and intent == "log":
            # These would be returned by the router if we modified it
            pass
        log_webhook_success(psid_hash, mid, intent, category, amount, duration_ms)

def log_event(request_id: str, psid: str, mid: str, route: str, duration_ms: float, outcome: str):
    """Log structured event information (legacy format)"""
    from utils.security import hash_psid
    psid_hash = hash_psid(psid)
    log_webhook_success(psid_hash, mid, outcome, None, None, duration_ms)

def process_webhook_fast(payload_bytes: bytes, signature: str, app_secret: str) -> tuple:
    """Fast webhook processing with signature verification and async handling"""
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    try:
        # Step 1: Verify signature (skip if no app_secret for MVP)
        if app_secret and not verify_webhook_signature(payload_bytes, signature, app_secret):
            duration_ms = (time.time() - start_time) * 1000
            log_event(request_id, "unknown", "unknown", "verify_signature", duration_ms, "invalid_signature")
            return "Invalid signature", 403
        
        # Step 2: Parse JSON payload
        try:
            data = json.loads(payload_bytes.decode('utf-8'))
        except json.JSONDecodeError:
            duration_ms = (time.time() - start_time) * 1000
            log_event(request_id, "unknown", "unknown", "parse_json", duration_ms, "invalid_json")
            return "Invalid JSON", 400
        
        # Step 3: Extract events
        events = extract_webhook_events(data)
        if not events:
            duration_ms = (time.time() - start_time) * 1000
            log_event(request_id, "unknown", "unknown", "extract_events", duration_ms, "no_events")
            return "EVENT_RECEIVED", 200
        
        # Step 4: Enqueue events for background processing  
        from .background_processor import background_processor
        
        events_queued = 0
        for event in events:
            psid = event['psid']
            mid = event['mid']
            text = event.get('text', '')
            
            # Check for duplicates
            if is_duplicate_message(mid):
                log_event(request_id, psid, mid, "dedupe_check", 0, "duplicate")
                continue
            
            # Enqueue for safe background processing
            if background_processor.enqueue_message(request_id, psid, mid, text):
                events_queued += 1
                log_event(request_id, psid, mid, "enqueue", 0, "queued")
            else:
                log_event(request_id, psid, mid, "enqueue", 0, "failed")
        
        # Return fast response (background processing continues)
        duration_ms = (time.time() - start_time) * 1000
        log_event(request_id, "batch", f"{len(events)}_events", "webhook_complete", duration_ms, "success")
        logger.info(f"Request {request_id}: Webhook processed in {duration_ms:.2f}ms, {events_queued} events queued")
        return "EVENT_RECEIVED", 200
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_event(request_id, "unknown", "unknown", "webhook_error", duration_ms, f"error:{str(e)[:50]}")
        logger.error(f"Webhook processing error: {str(e)}")
        return "EVENT_RECEIVED", 200  # Always return 200 to Facebook