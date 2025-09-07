"""Redis connectivity smoke test endpoint"""
import os
import time
import json
from flask import Blueprint, jsonify
from utils.logger import structured_logger

# Create blueprint
redis_smoke_bp = Blueprint('redis_smoke', __name__)

@redis_smoke_bp.route('/redis-smoke', methods=['GET'])
def redis_smoke_test():
    """
    Redis connectivity smoke test endpoint
    
    Returns:
        200: {"connected": true, "value": "<test_value>"}
        503: {"connected": false, "error": "<error_message>"}
    """
    start_time = time.time()
    connected = False
    error_msg = None
    value = None
    
    try:
        # Check if REDIS_URL is configured
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            error_msg = "missing REDIS_URL"
            return _log_and_respond(start_time, connected, error_msg, value)
        
        # Import redis with error handling
        try:
            import redis
        except ImportError:
            error_msg = "redis package not installed"
            return _log_and_respond(start_time, connected, error_msg, value)
        
        # Handle different Redis URL formats
        if not redis_url.startswith(('redis://', 'rediss://', 'unix://')):
            redis_url = f"redis://{redis_url}"
        
        # Create Redis client with 3s timeouts
        client = redis.from_url(
            redis_url,
            socket_connect_timeout=3,
            socket_timeout=3,
            decode_responses=True
        )
        
        # Test SET operation with 5s TTL
        test_key = "smoke:test"
        test_value = "ok"
        client.set(test_key, test_value, ex=5)
        
        # Test GET operation
        retrieved_value = client.get(test_key)
        
        # Success case
        connected = True
        value = retrieved_value
        
    except redis.ConnectionError as e:
        error_msg = f"redis connection failed: {str(e)}"
    except redis.TimeoutError as e:
        error_msg = f"redis timeout: {str(e)}"
    except redis.AuthenticationError as e:
        error_msg = f"redis authentication failed: {str(e)}"
    except redis.RedisError as e:
        error_msg = f"redis error: {str(e)}"
    except Exception as e:
        error_msg = f"unexpected error: {str(e)}"
    
    return _log_and_respond(start_time, connected, error_msg, value)

def _log_and_respond(start_time, connected, error_msg, value):
    """Helper to log and return response"""
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Log structured JSON
    log_data = {
        "event": "redis_smoke",
        "connected": connected,
        "latency_ms": latency_ms
    }
    if error_msg:
        log_data["error"] = error_msg
    
    structured_logger.logger.info(json.dumps(log_data))
    
    # Build response
    response_data = {
        "connected": connected
    }
    
    if connected:
        response_data["value"] = value
        status_code = 200
    else:
        response_data["error"] = error_msg
        status_code = 503
    
    return jsonify(response_data), status_code