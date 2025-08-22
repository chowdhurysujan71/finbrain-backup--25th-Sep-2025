"""
FinBrain Structured Telemetry System
Emits structured logs for tracking intent routing and expense logging
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger("finbrain.structured")

def emit_telemetry(telemetry_data: Dict[str, Any]):
    """
    Emit structured telemetry data for analytics and monitoring.
    
    Args:
        telemetry_data: Dictionary containing telemetry information
    """
    try:
        # Add structured marker for log parsing
        structured_log = {
            "type": "finbrain_telemetry",
            "timestamp": datetime.utcnow().isoformat(),
            **telemetry_data
        }
        
        # Emit as structured JSON log
        logger.info(f"STRUCTURED_TELEMETRY: {json.dumps(structured_log)}")
        
        # Future: Send to external analytics system
        # Could integrate with systems like:
        # - DataDog metrics
        # - Google Analytics
        # - Custom analytics dashboard
        
    except Exception as e:
        logger.warning(f"Failed to emit telemetry: {e}")
        # Never fail main application flow due to telemetry issues

def log_intent_decision(request_id: str, psid_hash: str, intent: str, reason: str, metadata: Dict = None):
    """Log intent routing decision for analysis"""
    emit_telemetry({
        "event": "intent_decision",
        "request_id": request_id,
        "psid_hash": psid_hash[:8] + "...",
        "intent": intent,
        "reason": reason,
        "metadata": metadata or {}
    })

def log_expense_success(request_id: str, psid_hash: str, amount: float, currency: str, category: str, idempotent: bool):
    """Log successful expense logging"""
    emit_telemetry({
        "event": "expense_logged",
        "request_id": request_id, 
        "psid_hash": psid_hash[:8] + "...",
        "amount": amount,
        "currency": currency,
        "category": category,
        "idempotent": idempotent
    })

def log_duplicate_detection(request_id: str, psid_hash: str, mid: str):
    """Log duplicate message detection"""
    emit_telemetry({
        "event": "duplicate_detected",
        "request_id": request_id,
        "psid_hash": psid_hash[:8] + "...", 
        "mid": mid
    })

def log_summary_request(request_id: str, psid_hash: str, reason: str):
    """Log summary request"""
    emit_telemetry({
        "event": "summary_requested",
        "request_id": request_id,
        "psid_hash": psid_hash[:8] + "...",
        "reason": reason
    })