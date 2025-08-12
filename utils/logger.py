"""
Production-ready structured JSON logging for FinBrain
Tracks all inbound requests and outbound Facebook Graph API calls
"""
import json
import time
import logging
import uuid
from functools import wraps
from flask import request, g
from datetime import datetime

class StructuredLogger:
    """Structured JSON logger for production observability"""
    
    def __init__(self):
        self.logger = logging.getLogger('finbrain.structured')
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_request_start(self, request_id, psid_hash=None, message_id=None):
        """Log incoming request start"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "request_start",
            "rid": request_id,
            "method": request.method,
            "route": request.endpoint or request.path,
            "user_agent": request.headers.get('User-Agent', ''),
            "content_length": request.content_length or 0
        }
        
        if psid_hash:
            log_data["psid_hash"] = psid_hash
        if message_id:
            log_data["mid"] = message_id
            
        self.logger.info(json.dumps(log_data))
    
    def log_request_end(self, request_id, status_code, duration_ms, psid_hash=None, message_id=None):
        """Log request completion with performance metrics"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "request_end",
            "rid": request_id,
            "status": status_code,
            "duration_ms": round(duration_ms, 2),
            "route": request.endpoint or request.path
        }
        
        if psid_hash:
            log_data["psid_hash"] = psid_hash
        if message_id:
            log_data["mid"] = message_id
            
        self.logger.info(json.dumps(log_data))
    
    def log_graph_api_call(self, request_id, endpoint, method="POST", status_code=None, duration_ms=None, error=None):
        """Log Facebook Graph API calls"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "graph_api_call",
            "rid": request_id,
            "endpoint": endpoint,
            "method": method
        }
        
        if status_code:
            log_data["status"] = status_code
        if duration_ms:
            log_data["duration_ms"] = round(duration_ms, 2)
        if error:
            log_data["error"] = str(error)
            
        self.logger.info(json.dumps(log_data))
    
    def log_webhook_processed(self, request_id, psid_hash, message_id, intent, category=None, amount=None, processing_ms=None):
        """Log successful webhook message processing"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "webhook_processed",
            "rid": request_id,
            "psid_hash": psid_hash,
            "mid": message_id,
            "intent": intent
        }
        
        if category:
            log_data["category"] = category
        if amount:
            log_data["amount"] = amount
        if processing_ms:
            log_data["processing_ms"] = round(processing_ms, 2)
            
        self.logger.info(json.dumps(log_data))

# Global structured logger instance
structured_logger = StructuredLogger()

def request_logger(f):
    """Decorator to automatically log request start/end with timing"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        g.request_id = request_id
        g.request_start_time = time.time()
        
        # Extract messaging context if available
        psid_hash = None
        message_id = None
        
        # For webhook requests, try to extract from request data
        if request.is_json and request.json:
            data = request.json
            if 'entry' in data and len(data['entry']) > 0:
                entry = data['entry'][0]
                if 'messaging' in entry and len(entry['messaging']) > 0:
                    messaging = entry['messaging'][0]
                    if 'sender' in messaging:
                        # We'll hash the PSID in the webhook processor
                        pass
                    if 'message' in messaging and 'mid' in messaging['message']:
                        message_id = messaging['message']['mid']
        
        # Log request start
        structured_logger.log_request_start(request_id, psid_hash, message_id)
        
        try:
            # Execute the actual route function
            response = f(*args, **kwargs)
            
            # Calculate duration
            duration_ms = (time.time() - g.request_start_time) * 1000
            
            # Get status code from response
            if hasattr(response, 'status_code'):
                status_code = response.status_code
            elif isinstance(response, tuple) and len(response) > 1:
                status_code = response[1]
            else:
                status_code = 200
            
            # Log successful completion
            structured_logger.log_request_end(request_id, status_code, duration_ms, psid_hash, message_id)
            
            return response
            
        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.time() - g.request_start_time) * 1000
            
            # Log error completion
            structured_logger.log_request_end(request_id, 500, duration_ms, psid_hash, message_id)
            
            # Re-raise the exception
            raise
    
    return decorated_function

def get_request_id():
    """Get current request ID from Flask g object"""
    return getattr(g, 'request_id', 'unknown')

def log_graph_call(endpoint, method="POST", status_code=None, duration_ms=None, error=None):
    """Convenience function to log Graph API calls with current request context"""
    request_id = get_request_id()
    structured_logger.log_graph_api_call(request_id, endpoint, method, status_code, duration_ms, error)

def log_webhook_success(psid_hash, message_id, intent, category=None, amount=None, processing_ms=None):
    """Convenience function to log successful webhook processing"""
    request_id = get_request_id()
    structured_logger.log_webhook_processed(request_id, psid_hash, message_id, intent, category, amount, processing_ms)