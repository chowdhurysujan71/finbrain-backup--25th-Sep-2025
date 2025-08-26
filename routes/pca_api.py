"""
PCA API Routes for Overlay System
Handles rule management, corrections, and precedence operations
"""

from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
import json
import logging
from typing import Dict, List, Any

from app import db
from models_pca import UserRule, UserCorrection, TransactionEffective
from utils.precedence_engine import precedence_engine
from utils.pca_feature_flags import pca_feature_flags
from utils.deterministic import ensure_hashed

logger = logging.getLogger("finbrain.pca_api")

# Create blueprint
pca_api = Blueprint('pca_api', __name__, url_prefix='/api')

@pca_api.before_request
def check_overlay_enabled():
    """Ensure overlay features are enabled for API access"""
    if not pca_feature_flags.is_overlay_active():
        return jsonify({
            'error': 'PCA overlay system is not active',
            'mode': pca_feature_flags.mode,
            'overlay_enabled': pca_feature_flags.overlay_enabled
        }), 503

@pca_api.route('/rules/create', methods=['POST'])
def create_rule():
    """Create a new user rule"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['category', 'merchant_pattern']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get user from session or header (implement based on your auth)
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        # Build pattern and rule_set
        pattern = {}
        if data.get('merchant_pattern'):
            pattern['store_name_contains'] = data['merchant_pattern']
        if data.get('vertical'):
            pattern['vertical'] = data['vertical']
        if data.get('text_contains'):
            pattern['text_contains'] = data['text_contains']
        if data.get('category_was'):
            pattern['category_was'] = data['category_was']
            
        rule_set = {
            'category': data['category']
        }
        if data.get('subcategory'):
            rule_set['subcategory'] = data['subcategory']
        
        # Create rule
        rule = UserRule(
            rule_id=f"rule_{user_id}_{int(datetime.now().timestamp())}",
            user_id=user_id,
            pattern_json=pattern,
            rule_set_json=rule_set,
            rule_name=data.get('rule_name', f"Auto-rule for {data['category']}"),
            scope=data.get('scope', 'future_only'),
            active=True
        )
        
        db.session.add(rule)
        db.session.commit()
        
        # Preview how many transactions this would affect
        preview_count = _preview_rule_impact(user_id, pattern, rule_set)
        
        logger.info(f"Created rule {rule.rule_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'rule_id': rule.rule_id,
            'preview_count': preview_count,
            'message': f'Rule created successfully. Will apply to {preview_count} transactions.'
        })
        
    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create rule'}), 500

@pca_api.route('/rules/<rule_id>/toggle', methods=['POST'])
def toggle_rule(rule_id):
    """Enable or disable a rule"""
    try:
        data = request.get_json()
        active = data.get('active', True)
        
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        rule = db.session.query(UserRule).filter_by(
            rule_id=rule_id,
            user_id=user_id
        ).first()
        
        if not rule:
            return jsonify({'error': 'Rule not found'}), 404
            
        rule.active = active
        rule.updated_at = datetime.utcnow()
        db.session.commit()
        
        action = "enabled" if active else "disabled"
        logger.info(f"Rule {rule_id} {action} by user {user_id}")
        
        return jsonify({
            'success': True,
            'rule_id': rule_id,
            'active': active,
            'message': f'Rule {action} successfully'
        })
        
    except Exception as e:
        logger.error(f"Error toggling rule {rule_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to toggle rule'}), 500

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