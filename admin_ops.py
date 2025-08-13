"""
Admin operations for runtime control
Real-time AI toggle and system monitoring
"""
from flask import Blueprint, request, jsonify
from functools import wraps
import os
import time

from flags import FLAGS, toggle_ai
from simple_router import simple_router
from ai_adapter import get_stats as get_ai_stats

admin_ops = Blueprint('admin_ops', __name__)

def require_admin(f):
    """Admin authentication decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        admin_user = os.environ.get('ADMIN_USER')
        admin_pass = os.environ.get('ADMIN_PASS')
        
        if not auth or auth.username != admin_user or auth.password != admin_pass:
            return jsonify({"error": "Authentication required"}), 401
            
        return f(*args, **kwargs)
    return decorated_function

@admin_ops.route("/ops/ai/toggle", methods=["POST"])
@require_admin
def toggle_ai_endpoint():
    """Toggle AI on/off at runtime"""
    data = request.get_json() or {}
    enabled = str(data.get("enabled", "")).lower() in ("1", "true", "yes", "on")
    
    old_state = FLAGS.ai_enabled
    new_state = toggle_ai(enabled)
    
    return jsonify({
        "ai_enabled": new_state,
        "previous_state": old_state,
        "changed": old_state != new_state
    })

@admin_ops.route("/ops/ai/status", methods=["GET"])
@require_admin  
def ai_status():
    """Get AI system status"""
    return jsonify({
        "ai_enabled": FLAGS.ai_enabled,
        "ai_adapter": get_ai_stats(),
        "router_stats": simple_router.get_telemetry()
    })

@admin_ops.route("/ops/telemetry", methods=["GET"])
@require_admin
def telemetry():
    """Streamlined telemetry endpoint"""
    return jsonify({
        "timestamp": time.time(),
        "ai_system": {
            "enabled": FLAGS.ai_enabled,
            "stats": get_ai_stats()
        },
        "routing": simple_router.get_telemetry(),
        "instant_toggle": True
    })