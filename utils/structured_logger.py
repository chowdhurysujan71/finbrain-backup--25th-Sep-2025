"""
Structured Logging System for FinBrain API
Provides JSON logging with trace IDs, request context, and security-safe messaging
"""

import logging
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from flask import request, g, has_request_context
import traceback
import sys

class StructuredLogger:
    """Enhanced logger with structured JSON output and security-safe messaging"""
    
    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)
    
    def _get_trace_id(self) -> str:
        """Get or generate trace ID for request correlation"""
        if has_request_context():
            if not hasattr(g, 'trace_id'):
                g.trace_id = str(uuid.uuid4())[:8]
            return g.trace_id
        return str(uuid.uuid4())[:8]
    
    def _get_request_context(self) -> Dict[str, Any]:
        """Extract safe request context for logging"""
        context = {}
        
        if has_request_context():
            context.update({
                "method": request.method,
                "endpoint": request.endpoint,
                "path": request.path,
                "remote_addr": request.environ.get('REMOTE_ADDR', 'unknown'),
                "user_agent": request.headers.get('User-Agent', 'unknown')[:200],
                "content_type": request.headers.get('Content-Type', 'unknown')
            })
            
            # Add sanitized user ID (never log full IDs for security)
            user_id = request.headers.get('X-User-ID')
            if user_id and len(user_id) > 8:
                context["user_id_prefix"] = user_id[:8] + "***"
            elif user_id:
                context["user_id_prefix"] = "short_id***"
        
        return context
    
    def _sanitize_error_data(self, data: Any) -> Any:
        """
        Sanitize error data to remove sensitive information
        Never log passwords, tokens, SQL queries, file paths, or stack traces
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                # Skip sensitive fields
                if any(sensitive in key.lower() for sensitive in 
                      ['password', 'token', 'secret', 'key', 'auth', 'session']):
                    sanitized[key] = "[REDACTED]"
                else:
                    sanitized[key] = self._sanitize_error_data(value)
            return sanitized
        
        elif isinstance(data, list):
            return [self._sanitize_error_data(item) for item in data]
        
        elif isinstance(data, str):
            # Remove file paths and system info
            if any(pattern in data.lower() for pattern in 
                  ['traceback', 'file "/', 'line ', 'module ', 'directory']):
                return "[SYSTEM_INFO_REDACTED]"
            # Truncate very long strings
            return data[:500] + "..." if len(data) > 500 else data
        
        return data
    
    def _create_log_entry(self, level: str, message: str, extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create structured log entry"""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
            "trace_id": self._get_trace_id(),
            "logger": self.logger.name
        }
        
        # Add request context
        request_context = self._get_request_context()
        if request_context:
            entry["request"] = request_context
        
        # Add extra data (sanitized)
        if extra_data:
            entry["data"] = self._sanitize_error_data(extra_data)
        
        return entry
    
    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log info level message with structured data"""
        entry = self._create_log_entry("INFO", message, extra_data)
        self.logger.info(json.dumps(entry))
    
    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log warning level message with structured data"""
        entry = self._create_log_entry("WARNING", message, extra_data)
        self.logger.warning(json.dumps(entry))
    
    def error(self, message: str, extra_data: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None):
        """Log error level message with structured data and optional exception"""
        entry = self._create_log_entry("ERROR", message, extra_data)
        
        # Add exception information (sanitized)
        if exception:
            entry["exception"] = {
                "type": type(exception).__name__,
                "message": self._sanitize_error_message(str(exception))
            }
        
        self.logger.error(json.dumps(entry))
    
    def critical(self, message: str, extra_data: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None):
        """Log critical level message with structured data"""
        entry = self._create_log_entry("CRITICAL", message, extra_data)
        
        if exception:
            entry["exception"] = {
                "type": type(exception).__name__,
                "message": self._sanitize_error_message(str(exception))
            }
        
        self.logger.critical(json.dumps(entry))
    
    def _sanitize_error_message(self, error_message: str) -> str:
        """Sanitize error message to remove system internals"""
        message = str(error_message)
        
        # Remove dangerous patterns
        dangerous_patterns = [
            ('traceback', '[STACK_TRACE_REMOVED]'),
            ('file "/', '[FILE_PATH_REMOVED]'),
            ('line ', '[LINE_INFO_REMOVED]'),
            ('module ', '[MODULE_INFO_REMOVED]'),
            ('sqlalchemy', '[SQL_ERROR_REMOVED]'),
            ('psycopg', '[DB_ERROR_REMOVED]'),
            ('postgres', '[DB_ERROR_REMOVED]'),
            ('permission denied', '[PERMISSION_ERROR_REMOVED]'),
            ('no such file', '[FILE_ERROR_REMOVED]')
        ]
        
        for pattern, replacement in dangerous_patterns:
            if pattern in message.lower():
                return replacement
        
        # Truncate very long messages
        return message[:300] + "..." if len(message) > 300 else message
    
    def log_api_request(self, success: bool = True, response_time: Optional[float] = None, extra_data: Optional[Dict[str, Any]] = None):
        """Log API request with performance metrics"""
        status = "SUCCESS" if success else "FAILED"
        message = f"API Request {status}"
        
        log_data = extra_data or {}
        if response_time is not None:
            log_data["response_time_ms"] = round(response_time * 1000, 2)
        
        if success:
            self.info(message, log_data)
        else:
            self.warning(message, log_data)
    
    def log_validation_error(self, field_errors: Dict[str, str], endpoint: str):
        """Log validation errors (info level since these are expected)"""
        message = f"Validation failed for {endpoint}"
        extra_data = {
            "validation_errors": field_errors,
            "error_count": len(field_errors)
        }
        self.info(message, extra_data)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security-related events at warning level"""
        message = f"Security Event: {event_type}"
        self.warning(message, {"security_event": details})
    
    def log_business_error(self, error_code: str, details: str, extra_data: Optional[Dict[str, Any]] = None):
        """Log business logic errors"""
        message = f"Business Error [{error_code}]: {details}"
        self.warning(message, extra_data)

# Global structured loggers for common use cases
api_logger = StructuredLogger("finbrain.api")
auth_logger = StructuredLogger("finbrain.auth") 
validation_logger = StructuredLogger("finbrain.validation")
security_logger = StructuredLogger("finbrain.security")

def log_api_error(error_code: str, message: str, extra_data: Optional[Dict[str, Any]] = None, exception: Optional[Exception] = None):
    """Convenience function to log API errors"""
    api_logger.error(f"[{error_code}] {message}", extra_data, exception)

def log_validation_failure(field_errors: Dict[str, str], endpoint: str):
    """Convenience function to log validation failures"""
    validation_logger.log_validation_error(field_errors, endpoint)

def log_auth_event(event_type: str, user_identifier: Optional[str] = None, success: bool = True):
    """Convenience function to log authentication events"""
    details = {"event_type": event_type, "success": success}
    if user_identifier:
        # Sanitize user identifier 
        details["user_prefix"] = user_identifier[:8] + "***" if len(user_identifier) > 8 else "short***"
    
    level_logger = auth_logger.info if success else auth_logger.warning
    level_logger(f"Auth Event: {event_type}", details)

def log_security_incident(incident_type: str, details: Dict[str, Any]):
    """Convenience function to log security incidents"""
    security_logger.log_security_event(incident_type, details)

# Flask request timing decorator
def log_request_timing(func):
    """Decorator to log request timing automatically"""
    def wrapper(*args, **kwargs):
        import time
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            api_logger.log_api_request(success=True, response_time=response_time)
            return result
        except Exception as e:
            response_time = time.time() - start_time
            api_logger.log_api_request(success=False, response_time=response_time, 
                                     extra_data={"error": str(e)})
            raise
    
    return wrapper