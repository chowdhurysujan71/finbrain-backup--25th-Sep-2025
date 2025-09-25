"""
Asset management routes for FinBrain
Provides secure file upload/download via Supabase Storage signed URLs
"""
import json
import os
import time

from flask import Blueprint, g, jsonify, request

from utils.logger import structured_logger

# Import storage client  
try:
    from app.storage_supabase import storage_client
except ImportError:
    # Handle case where app is not a package
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
    from storage_supabase import storage_client

# Create blueprint
assets_bp = Blueprint('assets', __name__, url_prefix='/assets')

# Configuration
ALLOWED_CONTENT_TYPES = {
    'image/png', 'image/jpeg', 'application/pdf', 
    'text/plain', 'application/json'
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
# Read delete flag dynamically for testing
def is_delete_enabled():
    return os.environ.get('ASSETS_ALLOW_DELETE', 'false').lower() == 'true'

def validate_user_context():
    """Validate user is authenticated via session"""
    user_id = getattr(g, 'user_id', None)
    if not user_id:
        return None, {"error": "Authentication required"}, 401
    return user_id, None, None

def validate_path_prefix(path: str, user_id: str):
    """Validate path starts with user_id prefix"""
    expected_prefix = f"{user_id}/"
    if not path.startswith(expected_prefix):
        return False, {"error": f"Path must start with '{expected_prefix}'"}, 403
    return True, None, None

def validate_content_type(content_type: str):
    """Validate content type is in allowlist"""
    if content_type not in ALLOWED_CONTENT_TYPES:
        return False, {
            "error": f"Content type '{content_type}' not allowed",
            "allowed_types": list(ALLOWED_CONTENT_TYPES)
        }, 400
    return True, None, None

def validate_file_size(size: int):
    """Validate file size is within limits"""
    if size > MAX_FILE_SIZE:
        return False, {
            "error": f"File size {size} exceeds maximum {MAX_FILE_SIZE} bytes"
        }, 400
    return True, None, None

def log_operation(op: str, user_id: str, path: str, status: int, latency_ms: float):
    """Log asset operation using structured logger"""
    log_data = {
        "ts": int(time.time() * 1000),
        "level": "info",
        "request_id": getattr(g, 'request_id', 'unknown'),
        "user_id": user_id,
        "path": path,
        "op": op,
        "status": status,
        "latency_ms": round(latency_ms, 2)
    }
    structured_logger.logger.info(json.dumps(log_data))

@assets_bp.route('/upload-url', methods=['POST'])
def upload_url():
    """Generate signed URL for file upload"""
    start_time = time.time()
    
    try:
        # Validate user context
        user_id, error_response, status_code = validate_user_context()
        if error_response:
            return jsonify(error_response), status_code
        
        # Validate JSON body
        if not request.is_json:
            return jsonify({"error": "JSON body required"}), 400
            
        data = request.get_json()
        
        # Extract required fields
        path = data.get('path')
        content_type = data.get('content_type')
        size = data.get('size')
        
        if not all([path, content_type, size is not None]):
            return jsonify({
                "error": "Missing required fields: path, content_type, size"
            }), 400
        
        # Validate path prefix
        valid, error_response, status_code = validate_path_prefix(path, user_id)
        if not valid:
            return jsonify(error_response), status_code
            
        # Validate content type
        valid, error_response, status_code = validate_content_type(content_type)
        if not valid:
            return jsonify(error_response), status_code
            
        # Validate file size
        valid, error_response, status_code = validate_file_size(size)
        if not valid:
            return jsonify(error_response), status_code
        
        # Generate upload URL
        result = storage_client.get_upload_url(path, content_type)
        
        latency_ms = (time.time() - start_time) * 1000
        log_operation("upload_url", user_id, path, 200, latency_ms)
        
        return jsonify(result), 200
        
    except Exception:
        latency_ms = (time.time() - start_time) * 1000
        safe_user_id = user_id if 'user_id' in locals() and user_id else "unknown"
        safe_path = path if 'path' in locals() and path else "unknown"
        log_operation("upload_url", safe_user_id, safe_path, 500, latency_ms)
        
        return jsonify({"error": "Internal server error"}), 500

@assets_bp.route('/download-url', methods=['GET'])
def download_url():
    """Generate signed URL for file download"""
    start_time = time.time()
    
    try:
        # Validate user context
        user_id, error_response, status_code = validate_user_context()
        if error_response:
            return jsonify(error_response), status_code
        
        # Get path from query params
        path = request.args.get('path')
        if not path:
            return jsonify({"error": "path query parameter required"}), 400
        
        # Validate path prefix
        valid, error_response, status_code = validate_path_prefix(path, user_id)
        if not valid:
            return jsonify(error_response), status_code
        
        # Generate download URL
        result = storage_client.get_download_url(path)
        
        latency_ms = (time.time() - start_time) * 1000
        log_operation("download_url", user_id, path, 200, latency_ms)
        
        return jsonify(result), 200
        
    except Exception:
        latency_ms = (time.time() - start_time) * 1000
        safe_user_id = user_id if 'user_id' in locals() and user_id else "unknown"
        safe_path = path if 'path' in locals() and path else "unknown"
        log_operation("download_url", safe_user_id, safe_path, 500, latency_ms)
        
        return jsonify({"error": "Internal server error"}), 500

@assets_bp.route('/', methods=['DELETE'])
def delete_asset():
    """Delete asset (feature-flagged)"""
    if not ASSETS_ALLOW_DELETE:
        return jsonify({"error": "Asset deletion not enabled"}), 403
        
    start_time = time.time()
    
    try:
        # Validate user context
        user_id, error_response, status_code = validate_user_context()
        if error_response:
            return jsonify(error_response), status_code
        
        # Get path from query params
        path = request.args.get('path')
        if not path:
            return jsonify({"error": "path query parameter required"}), 400
        
        # Validate path prefix
        valid, error_response, status_code = validate_path_prefix(path, user_id)
        if not valid:
            return jsonify(error_response), status_code
        
        # Delete object
        storage_client.delete_object(path)
        
        latency_ms = (time.time() - start_time) * 1000
        log_operation("delete", user_id, path, 200, latency_ms)
        
        return jsonify({"success": True, "path": path}), 200
        
    except Exception:
        latency_ms = (time.time() - start_time) * 1000
        safe_user_id = user_id if 'user_id' in locals() and user_id else "unknown"
        safe_path = path if 'path' in locals() and path else "unknown"
        log_operation("delete", safe_user_id, safe_path, 500, latency_ms)
        
        return jsonify({"error": "Internal server error"}), 500