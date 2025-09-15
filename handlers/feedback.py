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
        
    This function implements robust error handling and input validation
    """
    # Input validation
    if not user_id_hash or not isinstance(user_id_hash, str):
        logger.warning(f"Invalid user_id_hash provided: {user_id_hash}")
        return None
    
    if not text or not isinstance(text, str):
        logger.debug(f"Invalid text provided for feedback: {text}")
        return None
    
    try:
        from utils.feedback_context import get_feedback_context, clear_feedback_context
        from utils.structured import log_report_feedback
        from models import ReportFeedback
        from db_base import db
        
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
        
        # Optimized signal matching (most common patterns first)
        if normalized_text in ["YES", "Y", "👍"]:
            signal = "up"
        elif normalized_text in ["NO", "N", "👎"]:
            signal = "down"
        else:
            # Fallback to comprehensive matching for edge cases
            for pos_signal in positive_signals:
                if pos_signal in normalized_text:
                    signal = "up"
                    break
            
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
        
        # Optimized feedback storage  
        try:
            # Check for existing feedback first (faster than exception handling)
            existing = db.session.query(ReportFeedback).filter_by(
                user_id_hash=user_id_hash,
                report_context_id=report_context_id
            ).first()
            
            if existing:
                logger.info(f"Duplicate feedback ignored for context {report_context_id}")
            else:
                # Single database operation
                feedback = ReportFeedback(
                    user_id_hash=user_id_hash,
                    report_context_id=report_context_id,
                    signal=signal,
                    created_at=datetime.utcnow()
                )
                db.session.add(feedback)
                db.session.commit()
                logger.info(f"Feedback stored: {signal} for context {report_context_id}")
            
        except Exception as e:
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
        # Return None to indicate no feedback processed (not an error response)
        return None

def is_feedback_response(text: str) -> bool:
    """
    Ultra-fast check if text could be a feedback response
    Used for routing optimization
    """
    if not text or len(text.strip()) > 50:  # Feedback should be short
        return False
    
    # Fastest check for most common patterns
    normalized = text.strip().upper()
    return normalized in ["YES", "Y", "NO", "N", "👍", "👎"]
    
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