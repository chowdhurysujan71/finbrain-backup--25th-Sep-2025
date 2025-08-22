"""
Structured Telemetry System for FinBrain
Emits comprehensive telemetry for routing decisions and expense operations
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger("finbrain.structured")

def emit_telemetry(event_type: str, **data) -> None:
    """
    Emit structured telemetry with consistent format.
    
    Args:
        event_type: Type of event (intent, expense_logged, etc.)
        **data: Additional event data
    """
    try:
        # Create base telemetry structure
        telemetry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            **data
        }
        
        # Convert Decimal objects to float for JSON serialization
        def decimal_to_float(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            return obj
        
        # Clean the data for JSON serialization
        clean_data = {}
        for key, value in telemetry.items():
            clean_data[key] = decimal_to_float(value)
        
        # Emit structured log
        logger.info(f"TELEMETRY: {json.dumps(clean_data)}")
        
    except Exception as e:
        logger.warning(f"Failed to emit telemetry: {e}")

def log_intent_decision(psid_hash: str, mid: str, intent: str, reason: str, 
                       mode: str = "STD", details: str = "smart_nlp_v1") -> None:
    """
    Log intent routing decision.
    
    Args:
        psid_hash: User PSID hash (truncated for privacy)
        mid: Message ID 
        intent: Detected intent (LOG, SUMMARY, etc.)
        reason: Reason for intent decision
        mode: Processing mode (STD, AI)
        details: Additional details
    """
    emit_telemetry(
        event_type="intent",
        intent=intent,
        reason=reason,
        mode=mode,
        details=details,
        psid_hash=psid_hash[:8] + "...",
        mid=mid
    )

def log_expense_logged(psid_hash: str, mid: str, amount: Decimal, currency: str, 
                      category: str, merchant: Optional[str] = None,
                      idempotent: bool = False, mode: str = "STD") -> None:
    """
    Log successful expense logging.
    
    Args:
        psid_hash: User PSID hash
        mid: Message ID
        amount: Expense amount
        currency: Currency code
        category: Expense category
        merchant: Optional merchant name
        idempotent: Whether this was an idempotent operation
        mode: Processing mode
    """
    emit_telemetry(
        event_type="expense_logged",
        intent="LOG",
        amount=float(amount),
        currency=currency,
        category=category,
        merchant=merchant,
        idempotent=idempotent,
        mode=mode,
        details="smart_nlp_v1",
        psid_hash=psid_hash[:8] + "...",
        mid=mid
    )

def log_duplicate_detected(psid_hash: str, mid: str, amount: Optional[Decimal] = None,
                          currency: Optional[str] = None) -> None:
    """
    Log duplicate expense detection.
    
    Args:
        psid_hash: User PSID hash
        mid: Message ID that was duplicate
        amount: Optional amount for context
        currency: Optional currency for context
    """
    data = {
        "event_type": "duplicate",
        "intent": "LOG_DUP",
        "psid_hash": psid_hash[:8] + "...",
        "mid": mid
    }
    
    if amount is not None:
        data["amount"] = str(float(amount))
    if currency:
        data["currency"] = currency
    
    emit_telemetry(**data)

def log_summary_request(psid_hash: str, mid: str, reason: str, mode: str = "STD") -> None:
    """
    Log summary request.
    
    Args:
        psid_hash: User PSID hash
        mid: Message ID
        reason: Reason for summary (no_money_detected, explicit_request, etc.)
        mode: Processing mode
    """
    emit_telemetry(
        event_type="summary",
        intent="SUMMARY",
        reason=reason,
        mode=mode,
        psid_hash=psid_hash[:8] + "...",
        mid=mid
    )

def log_parsing_result(psid_hash: str, mid: str, text: str, 
                      parsed_data: Dict[str, Any], success: bool) -> None:
    """
    Log expense parsing result for debugging.
    
    Args:
        psid_hash: User PSID hash
        mid: Message ID
        text: Original text (truncated for privacy)
        parsed_data: Parsing result
        success: Whether parsing succeeded
    """
    emit_telemetry(
        event_type="parsing",
        success=success,
        text_length=len(text),
        text_preview=text[:50] + "..." if len(text) > 50 else text,
        parsed_amount=float(parsed_data.get('amount', 0)) if parsed_data.get('amount') else None,
        parsed_currency=parsed_data.get('currency'),
        parsed_category=parsed_data.get('category'),
        parsed_merchant=parsed_data.get('merchant'),
        psid_hash=psid_hash[:8] + "...",
        mid=mid
    )

def log_feature_flag_usage(psid_hash: str, flag_name: str, enabled: bool, 
                          reason: str = "default") -> None:
    """
    Log feature flag usage for canary tracking.
    
    Args:
        psid_hash: User PSID hash
        flag_name: Name of feature flag
        enabled: Whether flag was enabled for this user
        reason: Reason (default, allowlist, override)
    """
    emit_telemetry(
        event_type="feature_flag",
        flag_name=flag_name,
        enabled=enabled,
        reason=reason,
        psid_hash=psid_hash[:8] + "..."
    )

def log_router_performance(psid_hash: str, mid: str, operation: str, 
                          duration_ms: float, success: bool) -> None:
    """
    Log router performance metrics.
    
    Args:
        psid_hash: User PSID hash
        mid: Message ID
        operation: Operation name (money_detection, parsing, etc.)
        duration_ms: Operation duration in milliseconds
        success: Whether operation succeeded
    """
    emit_telemetry(
        event_type="performance",
        operation=operation,
        duration_ms=duration_ms,
        success=success,
        psid_hash=psid_hash[:8] + "...",
        mid=mid
    )

def log_error(psid_hash: str, mid: str, error_type: str, error_message: str,
             context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log errors with context for debugging.
    
    Args:
        psid_hash: User PSID hash
        mid: Message ID
        error_type: Type of error (parsing, db, routing, etc.)
        error_message: Error message (sanitized)
        context: Additional context
    """
    emit_telemetry(
        event_type="error",
        error_type=error_type,
        error_message=error_message[:200],  # Truncate for safety
        context=context or {},
        psid_hash=psid_hash[:8] + "...",
        mid=mid
    )