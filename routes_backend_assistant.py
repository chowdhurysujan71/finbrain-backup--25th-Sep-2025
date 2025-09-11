"""
Routes for FinBrain Backend Assistant API
Strict no-hallucination backend following exact specification
"""

from flask import Blueprint, request, jsonify
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
def api_get_totals():
    """
    POST /api/backend/get_totals
    Input: {"user_id": 123, "period": "week"}
    Output: {"period": "week", "total_minor": 50000, "top_category": "food", "expenses_count": 5}
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({"error": "Missing 'user_id' field"}), 400
        
        user_id = data['user_id']
        period = data.get('period', 'week')
        
        if period not in ['day', 'week', 'month']:
            return jsonify({"error": "Invalid period. Use: day, week, month"}), 400
        
        result = get_totals(user_id, period)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"get_totals API error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/get_recent_expenses', methods=['POST'])
def api_get_recent_expenses():
    """
    POST /api/backend/get_recent_expenses
    Input: {"user_id": 123, "limit": 10}
    Output: [{"id": 1, "description": "coffee", "amount_minor": 5000, "category": "food", "created_at": "..."}]
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({"error": "Missing 'user_id' field"}), 400
        
        user_id = data['user_id']
        limit = data.get('limit', 10)
        
        if limit <= 0 or limit > 100:
            limit = 10
        
        result = get_recent_expenses(user_id, limit)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"get_recent_expenses API error: {e}")
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
def api_user_summary():
    """
    POST /api/backend/user_summary
    Get user expense summary
    Input: {"user_id": 123, "period": "week"}
    Output: Summary from database only, never invented
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({"error": "Missing 'user_id' field"}), 400
        
        user_id = data['user_id']
        period = data.get('period', 'week')
        
        result = get_user_summary(user_id, period)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"user_summary API error: {e}")
        return jsonify({"error": "Internal server error"}), 500

@backend_api.route('/user_expenses', methods=['POST'])
def api_user_expenses():
    """
    POST /api/backend/user_expenses  
    Get recent user expenses
    Input: {"user_id": 123, "limit": 10}
    Output: Array of expenses from database only
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({"error": "Missing 'user_id' field"}), 400
        
        user_id = data['user_id']
        limit = data.get('limit', 10)
        
        result = get_user_expenses(user_id, limit)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"user_expenses API error: {e}")
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