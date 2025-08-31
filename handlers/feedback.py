"""
Report Feedback Handler
Processes YES/NO responses to Money Story reports
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

def handle_report_feedback(user_id_hash: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Handle YES/NO feedback responses to reports
    
    Args:
        user_id_hash: User identifier hash
        text: User message text
        
    Returns:
        Dict with response if feedback processed, None if not feedback
    """
    try:
        from utils.feedback_context import get_feedback_context, clear_feedback_context
        from utils.structured import log_report_feedback
        from models import ReportFeedback
        from app import db
        
        # Check if user has pending feedback context
        report_context_id = get_feedback_context(user_id_hash)
        
        if not report_context_id:
            # No pending feedback context - not a feedback response
            logger.debug(f"No feedback context for user {user_id_hash[:8]}...")
            return None
        
        # Normalize text for matching
        normalized_text = text.strip().upper()
        
        # Check for positive signals
        positive_signals = ["YES", "Y", "👍", "✅", "GOOD", "USEFUL", "HELPFUL", "হ্যাঁ", "ভালো"]
        negative_signals = ["NO", "N", "👎", "❌", "BAD", "NOT USEFUL", "NOT HELPFUL", "না", "খারাপ"]
        
        signal = None
        
        # Match positive feedback
        for pos_signal in positive_signals:
            if pos_signal in normalized_text:
                signal = "up"
                break
        
        # Match negative feedback (only if no positive match)
        if not signal:
            for neg_signal in negative_signals:
                if neg_signal in normalized_text:
                    signal = "down"
                    break
        
        # If no clear YES/NO detected, ignore (not feedback)
        if not signal:
            logger.debug(f"No clear feedback signal in: {text[:50]}...")
            return None
        
        logger.info(f"Feedback detected: {signal} from user {user_id_hash[:8]}... for context {report_context_id}")
        
        # Store feedback in database (idempotent)
        try:
            feedback = ReportFeedback()
            feedback.user_id_hash = user_id_hash
            feedback.report_context_id = report_context_id
            feedback.signal = signal
            feedback.created_at = datetime.utcnow()
            
            db.session.add(feedback)
            db.session.commit()
            
            logger.info(f"Feedback stored: {signal} for context {report_context_id}")
            
        except Exception as e:
            # Handle duplicate feedback (idempotency)
            if "unique constraint" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info(f"Duplicate feedback ignored for context {report_context_id}")
                db.session.rollback()
            else:
                logger.error(f"Failed to store feedback: {e}")
                db.session.rollback()
                # Continue with telemetry and response even if storage fails
        
        # Log telemetry event
        log_report_feedback(user_id_hash, report_context_id, signal)
        
        # Clear feedback context (feedback collected)
        clear_feedback_context(user_id_hash)
        
        # Generate confirmation response
        if signal == "up":
            response_text = "👍 Got it, thanks for your feedback!"
        else:  # signal == "down"
            response_text = "👎 Thanks — we'll use this to improve."
        
        return {
            "text": response_text,
            "intent": "report_feedback",
            "signal": signal,
            "report_context_id": report_context_id
        }
        
    except Exception as e:
        logger.error(f"Feedback handler error: {e}")
        return None

def is_feedback_response(text: str) -> bool:
    """
    Quick check if text could be a feedback response
    Used for fast routing decisions
    """
    if not text or len(text.strip()) > 50:  # Feedback should be short
        return False
    
    # Quick text normalization
    normalized = text.strip().upper()
    
    # Common feedback patterns
    feedback_patterns = [
        "YES", "Y", "NO", "N", 
        "👍", "👎", "✅", "❌",
        "GOOD", "BAD", "USEFUL", "NOT USEFUL",
        "হ্যাঁ", "না"  # Bengali yes/no
    ]
    
    for pattern in feedback_patterns:
        if pattern in normalized:
            return True
    
    return False