"""Fast Messenger webhook processing with signature verification and async handling"""
import hashlib
import hmac
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from .logger import log_webhook_success

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

def extract_webhook_events(data: dict[str, Any]) -> list:
    """Extract and validate webhook events using single-source-of-truth identity"""
    from .identity import extract_sender_psid, psid_hash
    
    events = []
    
    if not data or data.get('object') != 'page':
        return events
    
    for entry in data.get('entry', []):
        # Use canonical identity extraction - only processes message/postback events
        psid = extract_sender_psid({'entry': [entry]})
        if not psid:
            logger.debug("Skipping non-message event (delivery/read/etc)")
            continue
        
        # Compute hash once at intake
        user_hash = psid_hash(psid)
        
        for messaging in entry.get('messaging', []):
            # Skip events that don't have message content
            message = messaging.get('message', {})
            message_text = message.get('text', '')
            message_id = message.get('mid', '')
            
            if message_text and message_id:
                events.append({
                    'psid': psid,  # Always sender.id from canonical extraction
                    'text': message_text,
                    'mid': message_id,
                    'timestamp': messaging.get('timestamp', int(time.time() * 1000))
                })
    
    return events

def process_message_async(event: dict[str, Any], request_id: str):
    """Process message asynchronously with canonical identity (DEPRECATED - now using background processor)"""
    # This function is deprecated - background processor now handles message processing
    # Keeping for compatibility but it should not be called in the current architecture
    logger.warning("process_message_async called but deprecated - background processor should handle this")
    pass

def log_event(request_id: str, psid: str, mid: str, route: str, duration_ms: float, outcome: str):
    """Log structured event information (legacy format) - use hash if available"""
    # For legacy calls, compute hash if needed (this should be rare now)
    if len(psid) == 64:  # Already hashed
        user_hash = psid
    else:
        from .identity import psid_hash
        user_hash = psid_hash(psid)
    log_webhook_success(user_hash, mid, outcome, None, None, duration_ms)

def process_webhook_fast_local(payload_bytes: bytes) -> tuple[str, int]:
    """Local testing version that bypasses signature verification"""
    try:
        # Parse the payload
        payload_str = payload_bytes.decode('utf-8')
        data = json.loads(payload_str)
        
        # Extract messaging events  
        if data.get('object') != 'page':
            return "Not a page object", 400
            
        entries = data.get('entry', [])
        if not entries:
            return "No entries found", 400
            
        # Process events using same logic as production but skip signature
        events = extract_webhook_events(data)
        if not events:
            return "EVENT_RECEIVED", 200
            
        # Enqueue events for background processing  
        from .background_processor import background_processor
        
        events_queued = 0
        for event in events:
            psid = event['psid']
            mid = event['mid']
            text = event.get('text', '')
            
            # Check for duplicates
            if is_duplicate_message(mid):
                continue
            
            # Enqueue for safe background processing
            if background_processor.enqueue_message(f"local_{mid}", psid, mid, text):
                events_queued += 1
        
        logger.info(f"Local testing: processed {len(events)} events, {events_queued} queued")
        return "EVENT_RECEIVED", 200
        
    except Exception as e:
        logger.error(f"Local webhook processing error: {str(e)}")
        return "EVENT_RECEIVED", 200

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