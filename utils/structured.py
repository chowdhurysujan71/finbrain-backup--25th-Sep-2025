"""
Structured Logging and Telemetry for FinBrain
Comprehensive event tracking for AI corrections, routing, and system health
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("finbrain.structured")

def log_correction_detected(psid_hash: str, mid: str, event_type: str, status: str, feature_flag: str, version: str) -> None:
    """
    Log correction detection event.
    
    Args:
        psid_hash: User's PSID hash
        mid: Message ID
        event_type: Type of correction event
        status: Current status
        feature_flag: Feature flag name
        version: Correction system version
    """
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': 'correction_detected',
        'psid_hash': psid_hash[:8] + '...',
        'message_id': mid,
        'correction_type': event_type,
        'status': status,
        'feature_flag': feature_flag,
        'version': version
    }
    
    logger.info(f"CORRECTION_DETECTED {json.dumps(event)}")

def log_correction_no_candidate(psid_hash: str, mid: str, action: str) -> None:
    """
    Log when no correction candidate is found.
    
    Args:
        psid_hash: User's PSID hash
        mid: Message ID
        action: Action taken (e.g., 'logged_as_new')
    """
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': 'correction_no_candidate',
        'psid_hash': psid_hash[:8] + '...',
        'message_id': mid,
        'action': action
    }
    
    logger.info(f"CORRECTION_NO_CANDIDATE {json.dumps(event)}")

def log_correction_duplicate(psid_hash: str, mid: str) -> None:
    """
    Log duplicate correction attempt.
    
    Args:
        psid_hash: User's PSID hash
        mid: Message ID
    """
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': 'correction_duplicate',
        'psid_hash': psid_hash[:8] + '...',
        'message_id': mid
    }
    
    logger.warning(f"CORRECTION_DUPLICATE {json.dumps(event)}")

def log_correction_applied(psid_hash: str, mid: str, old_expense_id: int, new_expense_id: int, 
                          old_amount: float, new_amount: float, version: str) -> None:
    """
    Log successful correction application.
    
    Args:
        psid_hash: User's PSID hash
        mid: Message ID
        old_expense_id: ID of superseded expense
        new_expense_id: ID of new corrected expense
        old_amount: Original amount
        new_amount: Corrected amount
        version: Correction system version
    """
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': 'correction_applied',
        'psid_hash': psid_hash[:8] + '...',
        'message_id': mid,
        'old_expense_id': old_expense_id,
        'new_expense_id': new_expense_id,
        'old_amount': old_amount,
        'new_amount': new_amount,
        'amount_change': new_amount - old_amount,
        'version': version
    }
    
    logger.info(f"CORRECTION_APPLIED {json.dumps(event)}")

def log_routing_decision(psid_hash: str, text: str, intent: str, features_enabled: Dict[str, bool], 
                        processing_time_ms: float) -> None:
    """
    Log routing decision with feature flag context.
    
    Args:
        psid_hash: User's PSID hash
        text: Message text (truncated)
        intent: Detected intent
        features_enabled: Dict of feature flags and their states
        processing_time_ms: Processing time in milliseconds
    """
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': 'routing_decision',
        'psid_hash': psid_hash[:8] + '...',
        'text_preview': text[:50] + '...' if len(text) > 50 else text,
        'intent': intent,
        'features': features_enabled,
        'processing_time_ms': processing_time_ms
    }
    
    logger.info(f"ROUTING_DECISION {json.dumps(event)}")

def log_feature_flag_check(psid_hash: str, feature_name: str, enabled: bool, reason: str) -> None:
    """
    Log feature flag checks for debugging.
    
    Args:
        psid_hash: User's PSID hash
        feature_name: Name of the feature flag
        enabled: Whether the feature is enabled
        reason: Reason for the decision
    """
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': 'feature_flag_check',
        'psid_hash': psid_hash[:8] + '...',
        'feature_name': feature_name,
        'enabled': enabled,
        'reason': reason
    }
    
    logger.debug(f"FEATURE_FLAG_CHECK {json.dumps(event)}")

def log_money_detection_fallback(psid_hash: str, text: str, standard_result: bool, 
                                fallback_result: bool, fallback_reason: str) -> None:
    """
    Log money detection fallback usage.
    
    Args:
        psid_hash: User's PSID hash
        text: Message text (truncated)
        standard_result: Result from standard money detection
        fallback_result: Result from fallback detection
        fallback_reason: Reason for fallback activation
    """
    event = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': 'money_detection_fallback',
        'psid_hash': psid_hash[:8] + '...',
        'text_preview': text[:50] + '...' if len(text) > 50 else text,
        'standard_result': standard_result,
        'fallback_result': fallback_result,
        'fallback_reason': fallback_reason
    }
    
    logger.info(f"MONEY_DETECTION_FALLBACK {json.dumps(event)}")