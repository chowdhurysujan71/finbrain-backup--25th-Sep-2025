"""
Standardized Error Response System for FinBrain API
Provides consistent error formatting, security-safe messaging, and structured responses
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from flask import request, g
from datetime import datetime

logger = logging.getLogger(__name__)

# Standard error codes
class ErrorCodes:
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MISSING_FIELDS = "MISSING_FIELDS" 
    INVALID_FORMAT = "INVALID_FORMAT"
    
    # Authentication/Authorization errors
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    
    # Business logic errors
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    OPERATION_FAILED = "OPERATION_FAILED"
    
    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"

def generate_trace_id() -> str:
    """Generate unique trace ID for request tracking"""
    return str(uuid.uuid4())[:8]

def get_trace_id() -> str:
    """Get or create trace ID for current request"""
    if not hasattr(g, 'trace_id'):
        g.trace_id = generate_trace_id()
    return g.trace_id

def standardized_error_response(
    code: str, 
    message: str, 
    field_errors: Optional[Dict[str, str]] = None,
    status_code: int = 400,
    log_error: bool = True,
    context: Optional[Dict[str, Any]] = None
) -> tuple:
    """
    Create standardized error response with consistent format
    
    Args:
        code: Error code from ErrorCodes class
        message: User-friendly error message
        field_errors: Optional dict of field-specific validation errors
        status_code: HTTP status code
        log_error: Whether to log this error (disable for expected validation errors)
        context: Additional context for logging (sanitized)
    
    Returns:
        Tuple of (response_dict, status_code) for Flask jsonify
    """
    trace_id = get_trace_id()
    
    # Build response
    response = {
        "success": False,
        "code": code,
        "message": message,
        "trace_id": trace_id
    }
    
    # Add field errors if provided
    if field_errors:
        response["field_errors"] = field_errors
    
    # Log error if requested (skip validation errors to reduce noise)
    if log_error:
        log_context = {
            "trace_id": trace_id,
            "error_code": code,
            "status_code": status_code,
            "endpoint": request.endpoint,
            "method": request.method,
            "user_agent": request.headers.get('User-Agent', 'unknown')[:100]
        }
        
        # Add sanitized context
        if context:
            log_context.update(context)
        
        # Get sanitized user ID for logging (never log full IDs)
        user_id = request.headers.get('X-User-ID')
        if user_id:
            log_context["user_id_prefix"] = user_id[:8] + "***"
        
        logger.warning(f"API Error [{code}]: {message}", extra=log_context)
    
    return response, status_code

def validation_error_response(field_errors: Dict[str, str]) -> tuple:
    """Convenience method for validation errors with field-specific messages"""
    message = "Please fix the highlighted fields." if len(field_errors) > 1 else "Please fix the highlighted field."
    
    return standardized_error_response(
        code=ErrorCodes.VALIDATION_ERROR,
        message=message,
        field_errors=field_errors,
        status_code=400,
        log_error=False  # Validation errors are expected, don't log as warnings
    )

def missing_fields_error(missing_fields: List[str]) -> tuple:
    """Convenience method for missing required fields"""
    field_errors = {field: "This field is required" for field in missing_fields}
    
    return standardized_error_response(
        code=ErrorCodes.MISSING_FIELDS,
        message="Required fields are missing",
        field_errors=field_errors,
        status_code=400,
        log_error=False
    )

def unauthorized_error(message: str = "Authentication required") -> tuple:
    """Convenience method for authentication errors"""
    return standardized_error_response(
        code=ErrorCodes.UNAUTHORIZED,
        message=message,
        status_code=401,
        log_error=True
    )

def forbidden_error(message: str = "Access denied") -> tuple:
    """Convenience method for authorization errors"""
    return standardized_error_response(
        code=ErrorCodes.FORBIDDEN,
        message=message,
        status_code=403,
        log_error=True
    )

def internal_error(message: str = "An unexpected error occurred. Please try again.") -> tuple:
    """Convenience method for internal server errors"""
    return standardized_error_response(
        code=ErrorCodes.INTERNAL_ERROR,
        message=message,
        status_code=500,
        log_error=True
    )

def duplicate_resource_error(resource_type: str = "resource") -> tuple:
    """Convenience method for duplicate resource errors"""
    return standardized_error_response(
        code=ErrorCodes.DUPLICATE_RESOURCE,
        message=f"A {resource_type} with this information already exists",
        status_code=409,
        log_error=False
    )

def resource_not_found_error(resource_type: str = "resource") -> tuple:
    """Convenience method for resource not found errors"""
    return standardized_error_response(
        code=ErrorCodes.RESOURCE_NOT_FOUND,
        message=f"The requested {resource_type} was not found",
        status_code=404,
        log_error=False
    )

def safe_error_message(error: Exception, fallback: str = "An error occurred") -> str:
    """
    Extract safe error message from exception, sanitizing internal details
    Never expose stack traces, SQL errors, file paths, or system internals
    """
    error_str = str(error).lower()
    
    # Check for dangerous error patterns and return safe fallback
    dangerous_patterns = [
        'traceback', 'file "/', '\\', 'sql', 'database', 'connection',
        'psycopg', 'postgres', 'sqlalchemy', 'integrity', 'constraint',
        'permission denied', 'no such file', 'import error', 'module'
    ]
    
    for pattern in dangerous_patterns:
        if pattern in error_str:
            logger.warning(f"Unsafe error message sanitized: {error_str[:100]}")
            return fallback
    
    # Return original message if it appears safe
    return str(error) if len(str(error)) < 200 else fallback

def success_response(data: Any = None, message: str = "Operation completed successfully") -> dict:
    """
    Create standardized success response
    
    Args:
        data: Response data to include
        message: Success message
    
    Returns:
        Standardized success response dict
    """
    response = {
        "success": True,
        "message": message,
        "trace_id": get_trace_id()
    }
    
    if data is not None:
        response["data"] = data
    
    return response