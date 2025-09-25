"""
Emergency Panic Toggle System
Provides global emergency mode functionality for infrastructure security
"""
import logging
import os
from datetime import datetime
from typing import Any, Dict

from flask import jsonify

logger = logging.getLogger(__name__)

# Emergency mode configuration - checked at runtime for immediate response
EMERGENCY_MODE_ENABLED = os.environ.get('EMERGENCY_MODE', 'false').lower() in ['true', '1', 'enabled', 'on']
PANIC_TOGGLE_ENABLED = os.environ.get('PANIC_TOGGLE', 'false').lower() in ['true', '1', 'enabled', 'on'] 

# Emergency mode is active if either EMERGENCY_MODE or PANIC_TOGGLE is enabled
EMERGENCY_ACTIVE = EMERGENCY_MODE_ENABLED or PANIC_TOGGLE_ENABLED

def is_emergency_mode() -> bool:
    """
    Check if emergency mode is currently active
    Checks both EMERGENCY_MODE and PANIC_TOGGLE environment variables
    
    Returns:
        bool: True if emergency mode is active, False otherwise
    """
    # Re-check environment variables for dynamic updates
    emergency = os.environ.get('EMERGENCY_MODE', 'false').lower() in ['true', '1', 'enabled', 'on']
    panic = os.environ.get('PANIC_TOGGLE', 'false').lower() in ['true', '1', 'enabled', 'on']
    
    return emergency or panic

def get_safe_response(endpoint: str = "unknown", method: str = "GET") -> dict[str, Any]:
    """
    Generate a safe canned response for emergency mode
    
    Args:
        endpoint: The endpoint that was accessed
        method: The HTTP method used
        
    Returns:
        Dict: Safe JSON response
    """
    return {
        "status": "safe_mode",
        "message": "finbrain is temporarily in safe mode for maintenance",
        "timestamp": datetime.utcnow().isoformat(),
        "emergency_mode": True,
        "endpoint": endpoint,
        "method": method,
        "contact": "System administrator"
    }

def emergency_response(endpoint: str = "unknown", method: str = "GET", status_code: int = 503):
    """
    Create a Flask response for emergency mode
    
    Args:
        endpoint: The endpoint that was accessed
        method: The HTTP method used
        status_code: HTTP status code (default: 503 Service Unavailable)
        
    Returns:
        Flask response with safe content
    """
    response_data = get_safe_response(endpoint, method)
    
    # Log emergency mode access for monitoring
    logger.warning(f"EMERGENCY_MODE: {method} {endpoint} - serving safe response")
    
    return jsonify(response_data), status_code

def check_emergency_and_respond(endpoint_name: str, method: str = "GET"):
    """
    Decorator factory for emergency mode checking
    
    Args:
        endpoint_name: Name of the endpoint for logging
        method: HTTP method
        
    Returns:
        Decorator function that checks emergency mode before executing
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if is_emergency_mode():
                return emergency_response(endpoint_name, method)
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

def get_emergency_status() -> dict[str, Any]:
    """
    Get current emergency mode status and configuration
    
    Returns:
        Dict: Emergency mode status information
    """
    emergency_env = os.environ.get('EMERGENCY_MODE', 'false')
    panic_env = os.environ.get('PANIC_TOGGLE', 'false')
    
    return {
        "emergency_mode_active": is_emergency_mode(),
        "environment_variables": {
            "EMERGENCY_MODE": emergency_env,
            "PANIC_TOGGLE": panic_env
        },
        "triggers": {
            "emergency_mode_enabled": emergency_env.lower() in ['true', '1', 'enabled', 'on'],
            "panic_toggle_enabled": panic_env.lower() in ['true', '1', 'enabled', 'on']
        },
        "safe_response_ready": True,
        "timestamp": datetime.utcnow().isoformat()
    }

# Log initialization status
if EMERGENCY_ACTIVE:
    logger.warning("🚨 EMERGENCY MODE INITIALIZED - All requests will serve safe responses")
    logger.warning(f"Emergency triggers: EMERGENCY_MODE={EMERGENCY_MODE_ENABLED}, PANIC_TOGGLE={PANIC_TOGGLE_ENABLED}")
else:
    logger.info("Panic toggle system ready - emergency mode disabled")