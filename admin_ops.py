"""
Admin operations for runtime control
Real-time AI toggle and system monitoring
"""
from flask import Blueprint, request, jsonify
from functools import wraps
import os
import time

from flags import FLAGS, toggle_ai
from utils.production_router import production_router
from utils.ai_adapter_v2 import production_ai_adapter

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
    from utils.production_router import production_router as router, get_ai_stats
    return jsonify({
        "ai_enabled": FLAGS.ai_enabled,
        "ai_adapter": production_ai_adapter.get_stats() if hasattr(production_ai_adapter, 'get_stats') else {"status": "active"},
        "router_telemetry": router.get_telemetry()
    })

@admin_ops.route("/ops/ai/ping", methods=["GET"])
@require_admin
def ai_ping():
    """Sanity-check the AI adapter"""
    from utils.production_router import llm_generate
    
    if llm_generate is None:
        return jsonify({
            "ok": False,
            "error": "No AI provider configured",
            "latency_ms": 0,
            "reply": ""
        })
    
    r = llm_generate("Reply with the single word: PONG.")
    return jsonify({
        "ok": r["ok"], 
        "latency_ms": r.get("latency_ms"), 
        "reply": r.get("text", ""), 
        "error": r.get("error")
    })

@admin_ops.route("/ops/telemetry", methods=["GET"])
@require_admin
def telemetry():
    """Truth-telling telemetry - env vs runtime"""
    from utils.production_router import production_router as router
    return jsonify(router.get_telemetry())