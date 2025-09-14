"""
Routes for FinBrain Backend Assistant API
Strict no-hallucination backend following exact specification
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
from backend_assistant import (
    propose_expense, 
    add_expense,
    delete_expense,
    get_totals, 
    get_recent_expenses, 
    run_uat_checklist,
    get_sql_schemas,
    process_message,
    get_user_summary,
    get_user_expenses
)
from utils.error_responses import (
    standardized_error_response, internal_error, unauthorized_error,
    validation_error_response, success_response, ErrorCodes, safe_error_message
)
from utils.validators import APIValidator
from utils.structured_logger import api_logger, security_logger, log_validation_failure
import logging
import time
from datetime import datetime

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
    Uses standardized error responses and security logging.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_session_authenticated_user_id()
        
        if not user_id:
            # Log security event for unauthorized access
            security_logger.log_security_event("unauthorized_backend_access", {
                "endpoint": request.path,
                "method": request.method,
                "ip_address": request.environ.get('REMOTE_ADDR', 'unknown'),
                "user_agent": request.headers.get('User-Agent', 'unknown')[:200],
                "has_session": 'user_id' in session,
                "rejection_reason": "session_auth_required"
            })
            
            response, status_code = unauthorized_error(
                "Please log in through the web interface. Client headers are not accepted for financial endpoints."
            )
            return jsonify(response), status_code
        
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
    Enhanced with standardized error handling and validation
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        if not data.get('text') or not data.get('text').strip():
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Text is required for expense analysis",
                field_errors={"text": "Please provide expense text to analyze"},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        # Validate text length
        text = data['text'].strip()
        if len(text) > 1000:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Text is too long",
                field_errors={"text": "Text must be 1000 characters or less"},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        result = propose_expense(text)
        
        # Log successful analysis
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "text_length": len(text),
            "confidence": result.get('confidence', 0),
            "category": result.get('category', 'unknown')
        })
        
        return jsonify(success_response(result, "Expense analysis completed"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("Expense analysis error", {
            "error_type": type(e).__name__,
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to analyze expense text"))
        return jsonify(response), status_code

@backend_api.route('/add_expense', methods=['POST'])
@require_backend_user_auth
def api_add_expense(authenticated_user_id):
    """
    POST /api/backend/add_expense
    Input: {"amount_minor": 12300, "currency": "BDT", "category": "food", "description": "uat canary coffee", "source": "chat", "message_id": "optional"}
    Output: {"expense_id": 123, "correlation_id": "uuid", "amount_minor": 12300, "category": "food", "description": "...", "source": "chat", "idempotency_key": "api:hash"}
    Authentication: Required (session only - SECURITY HARDENED)
    Server sets: idempotency_key, amount_minor validation, correlation_id, source validation
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['amount_minor', 'currency', 'category', 'description', 'source']
        field_errors = {}
        
        for field in required_fields:
            if not data.get(field):
                if field == 'amount_minor':
                    field_errors[field] = "amount_minor is required and must be a positive integer"
                else:
                    field_errors[field] = f"{field} is required"
        
        # Validate amount_minor specifically
        amount_minor = data.get('amount_minor')
        if amount_minor is not None:
            if not isinstance(amount_minor, int) or amount_minor <= 0:
                field_errors['amount_minor'] = "amount_minor must be a positive integer (cents)"
        
        # Validate source
        source = data.get('source')
        if source and source not in {'chat', 'form', 'messenger'}:
            field_errors['source'] = "source must be one of: chat, form, messenger"
            
        if field_errors:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid expense data provided",
                field_errors=field_errors,
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        # Extract fields
        currency = data['currency']
        category = data['category']
        description = data['description']
        message_id = data.get('message_id')  # Optional
        
        # Call add_expense function with server-side field generation
        result = add_expense(
            user_id=authenticated_user_id,
            amount_minor=amount_minor,
            currency=currency,
            category=category,
            description=description,
            source=source,
            message_id=message_id
        )
        
        # Log successful expense creation with structured metrics
        response_time = (time.time() - start_time) * 1000
        
        # Enhanced structured metrics logging
        metrics_data = {
            "user_prefix": authenticated_user_id[:8] + "***",
            "amount_minor": amount_minor,
            "category": category,
            "source": source,
            "has_message_id": bool(message_id),
            "response_time_ms": response_time,
            # Additional structured metrics
            "amount_major": amount_minor / 100,
            "currency": currency,
            "expense_id": result["expense_id"],
            "correlation_id": result["correlation_id"][:8] + "...",
            "idempotency_key_prefix": result["idempotency_key"][:12] + "...",
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/api/backend/add_expense",
            "operation": "create_expense"
        }
        
        api_logger.log_api_request(True, response_time, metrics_data)
        
        # Additional structured metrics log for business analytics
        logger.info("EXPENSE_CREATED", extra={
            "structured_metrics": {
                "event_type": "expense_creation",
                "user_id_hash": authenticated_user_id,
                "amount_bdt": amount_minor / 100,
                "category": category,
                "source_channel": source,
                "expense_id": result["expense_id"],
                "processing_time_ms": response_time,
                "success": True
            }
        })
        
        return jsonify(success_response(result, "Expense added successfully"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("Add expense error", {
            "error_type": type(e).__name__,
            "user_prefix": authenticated_user_id[:8] + "***",
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to add expense"))
        return jsonify(response), status_code

@backend_api.route('/delete_expense', methods=['POST'])
@require_backend_user_auth
def api_delete_expense(authenticated_user_id):
    """
    POST /api/backend/delete_expense
    Input: {"expense_id": 123}
    Output: {"success": true, "expense_id": 123, "deleted_at": "...", "description": "..."}
    Authentication: Required (session only - SECURITY HARDENED)
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        expense_id = data.get('expense_id')
        if not expense_id:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="expense_id is required",
                field_errors={"expense_id": "expense_id is required"},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        # Validate expense_id type
        if not isinstance(expense_id, int) or expense_id <= 0:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid expense_id",
                field_errors={"expense_id": "expense_id must be a positive integer"},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        # Call delete_expense function
        result = delete_expense(
            user_id=authenticated_user_id,
            expense_id=expense_id
        )
        
        # Log successful deletion
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "user_prefix": authenticated_user_id[:8] + "***",
            "expense_id": expense_id,
            "operation": "delete"
        })
        
        return jsonify(success_response(result, "Expense deleted successfully"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("Delete expense error", {
            "error_type": type(e).__name__,
            "user_prefix": authenticated_user_id[:8] + "***",
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to delete expense"))
        return jsonify(response), status_code

@backend_api.route('/get_totals', methods=['POST'])
@require_backend_user_auth
def api_get_totals(authenticated_user_id):
    """
    POST /api/backend/get_totals
    Input: {"period": "week"}
    Output: {"period": "week", "total_minor": 50000, "top_category": "food", "expenses_count": 5}
    Authentication: Required (session only - SECURITY HARDENED)
    Enhanced with standardized error handling
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        period = data.get('period', 'week')
        
        # Validate period using new validation system
        period_error = APIValidator.validate_choice(period, "period", ['day', 'week', 'month'])
        if period_error:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid period specified",
                field_errors={"period": period_error},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        result = get_totals(authenticated_user_id, period)
        
        # Log successful request
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "user_prefix": authenticated_user_id[:8] + "***",
            "period": period,
            "total_expenses": result.get('expenses_count', 0)
        })
        
        return jsonify(success_response(result, f"Retrieved {period} totals"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("Get totals error", {
            "error_type": type(e).__name__,
            "user_prefix": authenticated_user_id[:8] + "***",
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to retrieve expense totals"))
        return jsonify(response), status_code

@backend_api.route('/get_recent_expenses', methods=['POST'])
@require_backend_user_auth
def api_get_recent_expenses(authenticated_user_id):
    """
    POST /api/backend/get_recent_expenses
    Input: {"limit": 10}
    Output: [{"id": 1, "description": "coffee", "amount_minor": 5000, "category": "food", "created_at": "..."}]
    Authentication: Required (session only - SECURITY HARDENED)
    Enhanced with standardized error handling
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        limit = data.get('limit', 10)
        
        # Validate limit using new validation system
        limit_error = APIValidator.validate_integer(limit, "limit", min_val=1, max_val=100)
        if limit_error:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid limit specified",
                field_errors={"limit": limit_error},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        result = get_recent_expenses(authenticated_user_id, int(limit))
        
        # Log successful request
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "user_prefix": authenticated_user_id[:8] + "***",
            "limit": limit,
            "expenses_returned": len(result) if isinstance(result, list) else 0
        })
        
        return jsonify(success_response(result, f"Retrieved {len(result) if isinstance(result, list) else 0} recent expenses"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("Get recent expenses error", {
            "error_type": type(e).__name__,
            "user_prefix": authenticated_user_id[:8] + "***",
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to retrieve recent expenses"))
        return jsonify(response), status_code

@backend_api.route('/uat_checklist', methods=['GET'])
def api_uat_checklist():
    """
    GET /api/backend/uat_checklist
    Runs UAT checklist and returns pass/fail results
    Enhanced with standardized error handling
    """
    start_time = time.time()
    
    try:
        result = run_uat_checklist()
        
        # Log successful request
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "operation": "uat_checklist",
            "checks_run": len(result) if isinstance(result, (list, dict)) else 0
        })
        
        return jsonify(success_response(result, "UAT checklist completed"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("UAT checklist error", {
            "error_type": type(e).__name__,
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to run UAT checklist"))
        return jsonify(response), status_code

@backend_api.route('/schemas', methods=['GET'])
def api_schemas():
    """
    GET /api/backend/schemas
    Returns SQL CREATE statements for all tables
    Enhanced with standardized error handling
    """
    start_time = time.time()
    
    try:
        schemas = get_sql_schemas()
        
        # Log successful request
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "operation": "get_schemas",
            "schema_count": len(schemas) if isinstance(schemas, dict) else 0
        })
        
        return jsonify(success_response(schemas, "Database schemas retrieved"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("Schemas API error", {
            "error_type": type(e).__name__,
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to retrieve database schemas"))
        return jsonify(response), status_code

@backend_api.route('/process_message', methods=['POST'])
def api_process_message():
    """
    POST /api/backend/process_message
    Main entry point for message processing
    Input: {"text": "I spent 50 on coffee"}
    Output: Expense proposal or "Not available in DB"
    Enhanced with standardized error handling
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        if not data.get('text') or not data.get('text').strip():
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Text is required for message processing",
                field_errors={"text": "Please provide text to process"},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        # Validate text length
        text = data['text'].strip()
        length_error = APIValidator.validate_string_length(text, "text", min_length=1, max_length=1000)
        if length_error:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid text length",
                field_errors={"text": length_error},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        result = process_message(text)
        
        # Log successful processing
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "text_length": len(text),
            "result_type": type(result).__name__
        })
        
        return jsonify(success_response(result, "Message processed successfully"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("Message processing error", {
            "error_type": type(e).__name__,
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to process message"))
        return jsonify(response), status_code

@backend_api.route('/user_summary', methods=['POST']) 
@require_backend_user_auth
def api_user_summary(authenticated_user_id):
    """
    POST /api/backend/user_summary
    Get user expense summary
    Input: {"period": "week"}
    Output: Summary from database only, never invented
    Authentication: Required (session only - SECURITY HARDENED)
    Enhanced with standardized error handling
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        period = data.get('period', 'week')
        
        # Validate period
        period_error = APIValidator.validate_choice(period, "period", ['day', 'week', 'month', 'year'])
        if period_error:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid period specified",
                field_errors={"period": period_error},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        result = get_user_summary(authenticated_user_id, period)
        
        # Log successful request
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "user_prefix": authenticated_user_id[:8] + "***",
            "period": period,
            "summary_type": "user_summary"
        })
        
        return jsonify(success_response(result, f"Retrieved {period} summary"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("User summary error", {
            "error_type": type(e).__name__,
            "user_prefix": authenticated_user_id[:8] + "***",
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to retrieve user summary"))
        return jsonify(response), status_code

@backend_api.route('/user_expenses', methods=['POST'])
@require_backend_user_auth
def api_user_expenses(authenticated_user_id):
    """
    POST /api/backend/user_expenses  
    Get recent user expenses
    Input: {"limit": 10}
    Output: Array of expenses from database only
    Authentication: Required (session only - SECURITY HARDENED)
    Enhanced with standardized error handling
    """
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        limit = data.get('limit', 10)
        
        # Validate limit
        limit_error = APIValidator.validate_integer(limit, "limit", min_val=1, max_val=100)
        if limit_error:
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid limit specified",
                field_errors={"limit": limit_error},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        result = get_user_expenses(authenticated_user_id, int(limit))
        
        # Log successful request
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "user_prefix": authenticated_user_id[:8] + "***",
            "limit": limit,
            "expenses_returned": len(result) if isinstance(result, list) else 0
        })
        
        return jsonify(success_response(result, f"Retrieved {len(result) if isinstance(result, list) else 0} user expenses"))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("User expenses error", {
            "error_type": type(e).__name__,
            "user_prefix": authenticated_user_id[:8] + "***",
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to retrieve user expenses"))
        return jsonify(response), status_code

# Health check endpoint
@backend_api.route('/health', methods=['GET'])
def api_health():
    """Backend assistant health check with standardized response format"""
    health_data = {
        "status": "healthy",
        "service": "FinBrain Backend Assistant",
        "version": "2.0-standardized-errors",
        "rules": [
            "Never invent, never hallucinate, never guess",
            "Only return SQL schemas or queries", 
            "Only return UAT checklists and audit steps",
            "Only return structured JSON matching schemas",
            "All numbers MUST come from database queries"
        ],
        "error_handling": {
            "standardized_format": True,
            "field_validation": True,
            "structured_logging": True,
            "security_sanitization": True
        }
    }
    
    return jsonify(success_response(health_data, "Backend assistant is healthy"))