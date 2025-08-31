"""
Structured Event Logging for PCA System
Phase 2: Enhanced telemetry and audit trails
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("finbrain.structured")

def log_structured_event(event_type: str, event_data: Dict[str, Any], 
                        user_id: Optional[str] = None) -> bool:
    """
    Log structured events for PCA telemetry and analysis
    
    Args:
        event_type: Type of event (PCA_MESSAGE_PROCESSED, PCA_CC_LOGGED, etc.)
        event_data: Event-specific data dictionary
        user_id: Optional user identifier (will be truncated for privacy)
        
    Returns:
        True if logged successfully, False otherwise
    """
    try:
        # Create structured log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'event_data': event_data
        }
        
        # Add user context if provided (privacy-safe)
        if user_id:
            log_entry['user_context'] = user_id[:12] + '...' if len(user_id) > 12 else user_id
        
        # Add system context
        from utils.pca_flags import pca_flags
        log_entry['system_context'] = {
            'pca_mode': pca_flags.mode.value,
            'kill_switch': pca_flags.global_kill_switch
        }
        
        # Log as structured JSON
        logger.info(f"STRUCTURED_EVENT: {json.dumps(log_entry, separators=(',', ':'))}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to log structured event {event_type}: {e}")
        return False

def log_correction_detected(user_hash: str, original_text: str, corrected_data: dict):
    """Log correction detection for analytics"""
    try:
        event_data = {
            "user_hash_prefix": user_hash[:8] + "...",
            "original_text": original_text[:50],
            "correction_type": corrected_data.get("type", "unknown"),
            "amount": corrected_data.get("amount"),
            "category": corrected_data.get("category")
        }
        
        log_structured_event("CORRECTION_DETECTED", event_data)
        
    except Exception as e:
        logger.warning(f"Failed to log correction detection: {e}")

def log_correction_no_candidate(user_hash: str, mid: str, reason: str):
    """Log when no correction candidate is found"""
    try:
        event_data = {
            "user_hash_prefix": user_hash[:8] + "...",
            "message_id": mid,
            "reason": reason
        }
        
        log_structured_event("CORRECTION_NO_CANDIDATE", event_data)
        
    except Exception as e:
        logger.warning(f"Failed to log correction no candidate: {e}")

def log_report_feedback(user_id_hash: str, report_context_id: str, signal: str):
    """Log report feedback event for analytics"""
    try:
        event_data = {
            "user_id": user_id_hash[:8] + "...",  # Match acceptance criteria format
            "report_context_id": report_context_id,
            "signal": signal,  # 'up' or 'down'
            "has_text": False  # Always false for YES/NO demo version
        }
        
        log_structured_event("report_feedback", event_data, user_id_hash)
        logger.info(f"Report feedback logged: {signal} for context {report_context_id}")
        
    except Exception as e:
        logger.warning(f"Failed to log report feedback: {e}")

def log_correction_duplicate(user_hash: str, mid: str, expense_id: str):
    """Log when correction is a duplicate"""
    try:
        event_data = {
            "user_hash_prefix": user_hash[:8] + "...",
            "message_id": mid,
            "expense_id": expense_id
        }
        
        log_structured_event("CORRECTION_DUPLICATE", event_data)
        
    except Exception as e:
        logger.warning(f"Failed to log correction duplicate: {e}")

def log_correction_applied(user_hash: str, mid: str, original_expense_id: str, new_expense_id: str, changes: dict):
    """Log when correction is successfully applied"""
    try:
        event_data = {
            "user_hash_prefix": user_hash[:8] + "...",
            "message_id": mid,
            "original_expense_id": original_expense_id,
            "new_expense_id": new_expense_id,
            "changes": changes
        }
        
        log_structured_event("CORRECTION_APPLIED", event_data)
        
    except Exception as e:
        logger.warning(f"Failed to log correction applied: {e}")

def log_cc_generation_event(cc_dict: Dict[str, Any], processing_time_ms: int, 
                           applied: bool = False) -> bool:
    """
    Log Canonical Command generation events for analysis
    
    Args:
        cc_dict: Complete CC dictionary
        processing_time_ms: Processing time in milliseconds
        applied: Whether CC was applied to create transactions
        
    Returns:
        True if logged successfully
    """
    try:
        event_data = {
            'cc_id': cc_dict.get('cc_id', ''),
            'intent': cc_dict.get('intent', ''),
            'confidence': cc_dict.get('confidence', 0.0),
            'decision': cc_dict.get('decision', ''),
            'processing_time_ms': processing_time_ms,
            'applied': applied,
            'model_version': cc_dict.get('model_version', 'unknown'),
            'has_clarifier': bool(cc_dict.get('clarifier', {}).get('type') != 'none')
        }
        
        # Extract slot summary (privacy-safe)
        slots = cc_dict.get('slots', {})
        if slots:
            slot_summary = {}
            if slots.get('amount'):
                slot_summary['has_amount'] = True
                slot_summary['amount_valid'] = isinstance(slots.get('amount'), (int, float))
            if slots.get('category'):
                slot_summary['has_category'] = True
            if slots.get('merchant_text'):
                slot_summary['has_merchant'] = True
            
            event_data['slot_summary'] = slot_summary
        
        return log_structured_event('PCA_CC_GENERATED', event_data)
        
    except Exception as e:
        logger.error(f"Failed to log CC generation event: {e}")
        return False

def log_shadow_mode_event(user_id: str, message_text: str, cc_result: Dict[str, Any]) -> bool:
    """
    Log SHADOW mode processing events for analysis
    
    Args:
        user_id: User identifier (will be truncated)
        message_text: Original message (truncated for privacy)
        cc_result: CC processing result
        
    Returns:
        True if logged successfully
    """
    try:
        event_data = {
            'message_length': len(message_text),
            'message_preview': message_text[:50] + '...' if len(message_text) > 50 else message_text,
            'cc_logged': cc_result.get('cc_logged', False),
            'intent_detected': cc_result.get('intent', 'none'),
            'confidence': cc_result.get('confidence', 0.0),
            'processing_time_ms': cc_result.get('processing_time_ms', 0),
            'error': bool(cc_result.get('error'))
        }
        
        return log_structured_event('PCA_SHADOW_MODE', event_data, user_id)
        
    except Exception as e:
        logger.error(f"Failed to log shadow mode event: {e}")
        return False

def log_routing_decision(user_id: str, message_text: str, intent: str, 
                        routing_path: str, processing_time_ms: float) -> bool:
    """
    Log routing decisions for analysis (compatibility with production router)
    
    Args:
        user_id: User identifier
        message_text: Original message 
        intent: Detected intent
        routing_path: Which routing path was taken
        processing_time_ms: Processing time
        
    Returns:
        True if logged successfully
    """
    try:
        event_data = {
            'intent': intent,
            'routing_path': routing_path,
            'processing_time_ms': processing_time_ms,
            'message_length': len(message_text),
            'message_preview': message_text[:30] + '...' if len(message_text) > 30 else message_text
        }
        
        return log_structured_event('ROUTING_DECISION', event_data, user_id)
        
    except Exception as e:
        logger.error(f"Failed to log routing decision: {e}")
        return False

def log_money_detection_fallback(user_id: str, message_text: str, 
                                fallback_reason: str) -> bool:
    """
    Log money detection fallback events (compatibility with production router)
    
    Args:
        user_id: User identifier
        message_text: Original message
        fallback_reason: Why money detection fell back
        
    Returns:
        True if logged successfully
    """
    try:
        event_data = {
            'fallback_reason': fallback_reason,
            'message_length': len(message_text),
            'message_preview': message_text[:30] + '...' if len(message_text) > 30 else message_text
        }
        
        return log_structured_event('MONEY_DETECTION_FALLBACK', event_data, user_id)
        
    except Exception as e:
        logger.error(f"Failed to log money detection fallback: {e}")
        return False