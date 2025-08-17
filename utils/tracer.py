"""
Simple event tracing for debugging write/read path inconsistencies
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def trace_event(event_type: str, **kwargs):
    """Log an event for tracing purposes"""
    timestamp = datetime.utcnow().isoformat()
    
    # Clean up user_id for logging - show first 8 chars for identification
    if 'user_id' in kwargs:
        user_id = kwargs['user_id']
        kwargs['user_id_preview'] = user_id[:8] + "..." if len(user_id) > 8 else user_id
        del kwargs['user_id']  # Remove full hash for privacy
    
    logger.info(f"TRACE [{event_type}] @ {timestamp} | {kwargs}")