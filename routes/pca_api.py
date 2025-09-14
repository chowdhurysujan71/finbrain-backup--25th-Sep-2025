"""
PCA API Routes for Overlay System
Handles rule management, corrections, and precedence operations
"""

from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
import json
import logging
import time
from typing import Dict, List, Any

from app import db
from models_pca import UserRule, UserCorrection, TransactionEffective
from utils.precedence_engine import precedence_engine
from utils.pca_feature_flags import pca_feature_flags
from utils.deterministic import ensure_hashed
from utils.error_responses import (
    standardized_error_response, internal_error, resource_not_found_error,
    validation_error_response, success_response, ErrorCodes, safe_error_message
)
from utils.validators import APIValidator
from utils.structured_logger import api_logger, log_validation_failure

logger = logging.getLogger("finbrain.pca_api")

# Create blueprint
pca_api = Blueprint('pca_api', __name__, url_prefix='/api')

@pca_api.before_request
def check_overlay_enabled():
    """Ensure overlay features are enabled for API access with standardized error response"""
    if not pca_feature_flags.is_overlay_active():
        response, status_code = standardized_error_response(
            code=ErrorCodes.SERVICE_UNAVAILABLE,
            message="PCA overlay system is not currently active",
            status_code=503,
            context={
                'mode': pca_feature_flags.mode,
                'overlay_enabled': pca_feature_flags.overlay_enabled
            }
        )
        return jsonify(response), status_code

@pca_api.route('/rules/create', methods=['POST'])
def create_rule():
    """Create a new user rule with comprehensive validation and standardized error handling"""
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        
        # Validate required fields with detailed error messages
        validation_errors = {}
        
        if not data.get('category'):
            validation_errors['category'] = 'Category is required for rule creation'
        elif not isinstance(data['category'], str) or len(data['category'].strip()) == 0:
            validation_errors['category'] = 'Category must be a non-empty string'
            
        if not data.get('merchant_pattern'):
            validation_errors['merchant_pattern'] = 'Merchant pattern is required for rule matching'
        elif not isinstance(data['merchant_pattern'], str) or len(data['merchant_pattern'].strip()) == 0:
            validation_errors['merchant_pattern'] = 'Merchant pattern must be a non-empty string'
        
        # Validate optional fields
        if data.get('rule_name'):
            name_error = APIValidator.validate_string_length(data['rule_name'], 'rule_name', max_length=100)
            if name_error:
                validation_errors['rule_name'] = name_error
        
        if data.get('scope') and data['scope'] not in ['future_only', 'all_transactions']:
            validation_errors['scope'] = 'Scope must be either "future_only" or "all_transactions"'
        
        if validation_errors:
            log_validation_failure(validation_errors, "pca_rule_creation")
            response, status_code = validation_error_response(validation_errors)
            return jsonify(response), status_code
        
        # Get user from session or header (implement based on your auth)
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        # Build pattern and rule_set
        pattern = {
            'store_name_contains': data['merchant_pattern'].strip()
        }
        if data.get('vertical'):
            pattern['vertical'] = data['vertical'].strip()
        if data.get('text_contains'):
            pattern['text_contains'] = data['text_contains'].strip()
        if data.get('category_was'):
            pattern['category_was'] = data['category_was'].strip()
            
        rule_set = {
            'category': data['category'].strip()
        }
        if data.get('subcategory'):
            rule_set['subcategory'] = data['subcategory'].strip()
        
        # Create rule
        rule = UserRule(
            rule_id=f"rule_{user_id}_{int(datetime.now().timestamp())}",
            user_id=user_id,
            pattern_json=pattern,
            rule_set_json=rule_set,
            rule_name=data.get('rule_name', f"Auto-rule for {data['category']}").strip(),
            scope=data.get('scope', 'future_only'),
            active=True
        )
        
        db.session.add(rule)
        db.session.commit()
        
        # Preview how many transactions this would affect
        preview_count = _preview_rule_impact(user_id, pattern, rule_set)
        
        # Log successful creation
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "rule_id": rule.rule_id,
            "user_prefix": user_id[:8] + "***",
            "category": rule_set['category'],
            "preview_count": preview_count
        })
        
        result_data = {
            'rule_id': rule.rule_id,
            'preview_count': preview_count,
            'rule_name': rule.rule_name,
            'active': rule.active
        }
        
        return jsonify(success_response(result_data, f'Rule created successfully. Will apply to {preview_count} transactions.'))
        
    except Exception as e:
        db.session.rollback()
        response_time = (time.time() - start_time) * 1000
        api_logger.error("PCA rule creation error", {
            "error_type": type(e).__name__,
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to create rule"))
        return jsonify(response), status_code

@pca_api.route('/rules/<rule_id>/toggle', methods=['POST'])
def toggle_rule(rule_id):
    """Enable or disable a rule with standardized error handling"""
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        
        # Validate rule_id parameter
        if not rule_id or not rule_id.strip():
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid rule ID",
                field_errors={"rule_id": "Rule ID is required and cannot be empty"},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        # Validate active parameter if provided
        active = data.get('active', True)
        if not isinstance(active, bool):
            response, status_code = standardized_error_response(
                code=ErrorCodes.VALIDATION_ERROR,
                message="Invalid active status",
                field_errors={"active": "Active status must be true or false"},
                status_code=400,
                log_error=False
            )
            return jsonify(response), status_code
        
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        rule = db.session.query(UserRule).filter_by(
            rule_id=rule_id.strip(),
            user_id=user_id
        ).first()
        
        if not rule:
            response, status_code = resource_not_found_error("rule")
            return jsonify(response), status_code
            
        rule.active = active
        rule.updated_at = datetime.utcnow()
        db.session.commit()
        
        action = "enabled" if active else "disabled"
        
        # Log successful toggle
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "rule_id": rule_id,
            "user_prefix": user_id[:8] + "***",
            "action": action,
            "active": active
        })
        
        result_data = {
            'rule_id': rule_id,
            'active': active,
            'rule_name': rule.rule_name
        }
        
        return jsonify(success_response(result_data, f'Rule {action} successfully'))
        
    except Exception as e:
        db.session.rollback()
        response_time = (time.time() - start_time) * 1000
        api_logger.error("PCA rule toggle error", {
            "error_type": type(e).__name__,
            "rule_id": rule_id,
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to toggle rule"))
        return jsonify(response), status_code

@pca_api.route('/rules/<rule_id>/preview', methods=['GET'])
def preview_rule(rule_id):
    """Preview the impact of a rule"""
    try:
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        rule = db.session.query(UserRule).filter_by(
            rule_id=rule_id,
            user_id=user_id
        ).first()
        
        if not rule:
            return jsonify({'error': 'Rule not found'}), 404
        
        # Get sample transactions that would be affected
        affected_transactions = _get_affected_transactions(
            user_id, 
            rule.pattern_json, 
            rule.rule_set_json,
            limit=10
        )
        
        return jsonify({
            'rule_id': rule_id,
            'rule_name': rule.rule_name,
            'count': len(affected_transactions),
            'transactions': affected_transactions,
            'pattern': rule.pattern_json,
            'rule_set': rule.rule_set_json
        })
        
    except Exception as e:
        logger.error(f"Error previewing rule {rule_id}: {e}")
        return jsonify({'error': 'Failed to preview rule'}), 500

@pca_api.route('/rules', methods=['GET'])
def list_rules():
    """List all user rules"""
    try:
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        rules = db.session.query(UserRule).filter_by(user_id=user_id).order_by(
            UserRule.created_at.desc()
        ).all()
        
        rules_data = []
        for rule in rules:
            rules_data.append({
                'id': rule.id,
                'rule_id': rule.rule_id,
                'rule_name': rule.rule_name,
                'pattern': rule.pattern_json,
                'rule_set': rule.rule_set_json,
                'active': rule.active,
                'created_at': rule.created_at.isoformat(),
                'last_applied': rule.last_applied.isoformat() if rule.last_applied else None,
                'application_count': rule.application_count
            })
        
        return jsonify({
            'rules': rules_data,
            'total': len(rules_data)
        })
        
    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        return jsonify({'error': 'Failed to list rules'}), 500

@pca_api.route('/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """Delete a user rule"""
    try:
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        rule = db.session.query(UserRule).filter_by(
            rule_id=rule_id,
            user_id=user_id
        ).first()
        
        if not rule:
            return jsonify({'error': 'Rule not found'}), 404
        
        db.session.delete(rule)
        db.session.commit()
        
        logger.info(f"Rule {rule_id} deleted by user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Rule deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting rule {rule_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete rule'}), 500

@pca_api.route('/corrections/create', methods=['POST'])
def create_correction():
    """Create a manual correction for a transaction"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['tx_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        # Build correction fields
        fields = {}
        for field in ['category', 'subcategory', 'amount', 'merchant_text']:
            if field in data:
                fields[field] = data[field]
        
        if not fields:
            return jsonify({'error': 'No correction fields provided'}), 400
        
        # Create correction
        correction = UserCorrection(
            correction_id=f"corr_{user_id}_{int(datetime.now().timestamp())}",
            user_id=user_id,
            tx_id=data['tx_id'],
            fields_json=fields,
            reason=data.get('reason', 'Manual correction'),
            correction_type='manual'
        )
        
        db.session.add(correction)
        db.session.commit()
        
        logger.info(f"Created correction {correction.correction_id} for tx {data['tx_id']}")
        
        return jsonify({
            'success': True,
            'correction_id': correction.correction_id,
            'message': 'Correction created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating correction: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create correction'}), 500

@pca_api.route('/transactions/<tx_id>/effective', methods=['GET'])
def get_effective_transaction(tx_id):
    """Get the effective view of a transaction"""
    try:
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        # Get raw transaction (implement based on your data model)
        raw_expense = _get_raw_transaction(tx_id)
        
        if not raw_expense:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Get effective view through precedence engine
        effective = precedence_engine.get_effective_view(
            user_id=user_id,
            tx_id=tx_id,
            raw_expense=raw_expense
        )
        
        return jsonify({
            'tx_id': tx_id,
            'original': raw_expense,
            'effective': effective.to_dict(),
            'source': effective.source
        })
        
    except Exception as e:
        logger.error(f"Error getting effective transaction {tx_id}: {e}")
        return jsonify({'error': 'Failed to get effective transaction'}), 500

def _preview_rule_impact(user_id: str, pattern: Dict, rule_set: Dict) -> int:
    """Preview how many transactions a rule would affect"""
    try:
        # This would query your expense table to count matches
        # For now, return a placeholder count
        return 5  # Replace with actual count logic
    except Exception:
        return 0

def _get_affected_transactions(user_id: str, pattern: Dict, rule_set: Dict, limit: int = 10) -> List[Dict]:
    """Get sample transactions that would be affected by a rule"""
    try:
        # This would query your expense table for matching transactions
        # For now, return sample data
        return [
            {
                'tx_id': 'tx_123',
                'merchant_text': 'Starbucks Coffee',
                'old_category': 'food',
                'new_category': rule_set.get('category', 'unknown'),
                'amount': 250
            }
        ]
    except Exception:
        return []

def _get_raw_transaction(tx_id: str) -> Dict:
    """Get raw transaction data"""
    try:
        # This would query your expense table
        # For now, return sample data
        return {
            'tx_id': tx_id,
            'amount': 100,
            'category': 'food',
            'merchant_text': 'Sample Restaurant',
            'timestamp': datetime.now().isoformat()
        }
    except Exception:
        return None