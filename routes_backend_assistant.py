"""
Routes for FinBrain Backend Assistant API
Strict no-hallucination backend following exact specification
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from backend_assistant import (
    propose_expense, 
    get_totals, 
    get_recent_expenses, 
    run_uat_checklist,
    get_sql_schemas,
    process_message,
    get_user_summary,
    get_user_expenses
)
import logging

logger = logging.getLogger(__name__)

backend_api = Blueprint('backend_api', __name__, url_prefix='/api/backend')

def get_session_authenticated_user_id():
    """Get authenticated user ID from server-side session only (SECURITY HARDENED).
    
    This function ONLY accepts session['user_id'] from proper server-side authentication.
    X-User-ID headers are REJECTED to prevent user impersonation attacks.
    Financial endpoints require proper login through the web interface.
    """
    # SECURITY: Only accept server-side session authentication
    # Never trust client-supplied headers for financial data access
    return session.get('user_id')

def require_backend_user_auth(f):
    """Backend API session-only authentication decorator (SECURITY HARDENED).
    
    Requires proper server-side session authentication. Client headers are rejected
    to prevent user impersonation attacks on financial endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_session_authenticated_user_id()
        
        if not user_id:
            logger.warning(f"Unauthorized access attempt to {request.path} - session auth required")
            return jsonify({
                "error": "Session authentication required", 
                "message": "Please log in through the web interface. Client headers are not accepted for financial endpoints.",
                "security_note": "X-User-ID headers rejected to prevent user impersonation"
            }), 401
        
        # Pass authenticated user_id to the route function
        kwargs['authenticated_user_id'] = user_id
        return f(*args, **kwargs)
    return decorated_function

@backend_api.route('/propose_expense', methods=['POST'])
def api_propose_expense():
    """
    POST /api/backend/propose_expense
    Input: {"text": "I spent 300 on lunch"}
    Output: {"amount_minor": 30000, "currency": "BDT", "category": "food", "confidence": 0.8}
    """
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' field"}), 400
        
        result = propose_expense(data['text'])
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"propose_expense API error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/get_totals', methods=['POST'])
@require_backend_user_auth
def api_get_totals(authenticated_user_id):
    """
    POST /api/backend/get_totals
    Input: {"period": "week"}
    Output: {"period": "week", "total_minor": 50000, "top_category": "food", "expenses_count": 5}
    Authentication: Required (session only - SECURITY HARDENED)
    """
    try:
        data = request.get_json() or {}
        period = data.get('period', 'week')
        
        if period not in ['day', 'week', 'month']:
            return jsonify({"error": "Invalid period. Use: day, week, month"}), 400
        
        result = get_totals(authenticated_user_id, period)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"get_totals API error for user {authenticated_user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/get_recent_expenses', methods=['POST'])
@require_backend_user_auth
def api_get_recent_expenses(authenticated_user_id):
    """
    POST /api/backend/get_recent_expenses
    Input: {"limit": 10}
    Output: [{"id": 1, "description": "coffee", "amount_minor": 5000, "category": "food", "created_at": "..."}]
    Authentication: Required (session only - SECURITY HARDENED)
    """
    try:
        data = request.get_json() or {}
        limit = data.get('limit', 10)
        
        if limit <= 0 or limit > 100:
            limit = 10
        
        result = get_recent_expenses(authenticated_user_id, limit)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"get_recent_expenses API error for user {authenticated_user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/uat_checklist', methods=['GET'])
def api_uat_checklist():
    """
    GET /api/backend/uat_checklist
    Runs UAT checklist and returns pass/fail results
    """
    try:
        result = run_uat_checklist()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"UAT checklist error: {e}")
        return jsonify({"error": "Internal server error", "timestamp": str(e)}), 500

@backend_api.route('/schemas', methods=['GET'])
def api_schemas():
    """
    GET /api/backend/schemas
    Returns SQL CREATE statements for all tables
    """
    try:
        schemas = get_sql_schemas()
        return jsonify(schemas)
        
    except Exception as e:
        logger.error(f"Schemas API error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/process_message', methods=['POST'])
def api_process_message():
    """
    POST /api/backend/process_message
    Main entry point for message processing
    Input: {"text": "I spent 50 on coffee"}
    Output: Expense proposal or "Not available in DB"
    """
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Missing 'text' field"}), 400
        
        result = process_message(data['text'])
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"process_message API error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/user_summary', methods=['POST']) 
@require_backend_user_auth
def api_user_summary(authenticated_user_id):
    """
    POST /api/backend/user_summary
    Get user expense summary
    Input: {"period": "week"}
    Output: Summary from database only, never invented
    Authentication: Required (session only - SECURITY HARDENED)
    """
    try:
        data = request.get_json() or {}
        period = data.get('period', 'week')
        
        result = get_user_summary(authenticated_user_id, period)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"user_summary API error for user {authenticated_user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/user_expenses', methods=['POST'])
@require_backend_user_auth
def api_user_expenses(authenticated_user_id):
    """
    POST /api/backend/user_expenses  
    Get recent user expenses
    Input: {"limit": 10}
    Output: Array of expenses from database only
    Authentication: Required (session only - SECURITY HARDENED)
    """
    try:
        data = request.get_json() or {}
        limit = data.get('limit', 10)
        
        result = get_user_expenses(authenticated_user_id, limit)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"user_expenses API error for user {authenticated_user_id}: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Health check endpoint
@backend_api.route('/health', methods=['GET'])
def api_health():
    """Backend assistant health check"""
    return jsonify({
        "status": "healthy",
        "service": "FinBrain Backend Assistant",
        "rules": [
            "Never invent, never hallucinate, never guess",
            "Only return SQL schemas or queries", 
            "Only return UAT checklists and audit steps",
            "Only return structured JSON matching schemas",
            "All numbers MUST come from database queries"
        ]
    })