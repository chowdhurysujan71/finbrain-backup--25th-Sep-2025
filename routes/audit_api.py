"""
Audit Transparency API
Phase 1: Read-only endpoints for dual-view (original + corrected)
Safe implementation with feature flags and caching
"""

import time

from flask import Blueprint, jsonify, request

from db_base import db
from models import Expense
from models_pca import UserCorrection
from utils.deterministic import ensure_hashed
from utils.pca_feature_flags import pca_feature_flags
from utils.precedence_engine import precedence_engine

audit_api = Blueprint('audit_api', __name__, url_prefix='/api/audit')

# Simple cache for audit queries (TTL: 60 seconds)
_audit_cache = {}
_cache_ttl = 60  # seconds

def get_cache_key(user_id, tx_id):
    """Generate cache key for audit query"""
    return f"audit_{user_id}_{tx_id}"

def get_cached_result(user_id, tx_id):
    """Get cached audit result if available and not expired"""
    cache_key = get_cache_key(user_id, tx_id)
    if cache_key in _audit_cache:
        entry = _audit_cache[cache_key]
        if time.time() - entry['timestamp'] < _cache_ttl:
            return entry['data']
    return None

def set_cache_result(user_id, tx_id, data):
    """Cache audit result with timestamp"""
    cache_key = get_cache_key(user_id, tx_id)
    _audit_cache[cache_key] = {
        'timestamp': time.time(),
        'data': data
    }
    # Clean old entries (simple cleanup)
    if len(_audit_cache) > 100:
        current_time = time.time()
        expired_keys = [k for k, v in _audit_cache.items() 
                       if current_time - v['timestamp'] > _cache_ttl]
        for key in expired_keys:
            del _audit_cache[key]

@audit_api.route('/transactions/<tx_id>', methods=['GET'])
def get_transaction_audit(tx_id):
    """
    Get audit view of a transaction (original + corrected)
    Returns both raw and effective views for audit transparency
    """
    start_time = time.time()
    
    # Check if audit feature is enabled
    if not pca_feature_flags.should_show_audit_ui():
        return jsonify({
            'error': 'Audit UI not enabled',
            'show_audit_ui': False
        }), 404
    
    # Get user_id from request (would come from auth in production)
    user_id = request.args.get('user_id', 'anonymous')
    user_id_hash = ensure_hashed(user_id)
    
    # Check cache first
    cached = get_cached_result(user_id_hash, tx_id)
    if cached:
        response_time_ms = (time.time() - start_time) * 1000
        cached['performance'] = {'response_time_ms': response_time_ms, 'cached': True}
        return jsonify(cached)
    
    try:
        # Get raw expense
        raw_expense = db.session.query(Expense).filter_by(
            transaction_id=tx_id
        ).first()
        
        if not raw_expense:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Convert to dict for processing
        raw_data = {
            'transaction_id': raw_expense.transaction_id,
            'amount': float(raw_expense.amount) if raw_expense.amount else 0,
            'category': raw_expense.category,
            'subcategory': raw_expense.subcategory,
            'merchant_text': raw_expense.merchant_text,
            'note': raw_expense.note,
            'expense_date': raw_expense.expense_date.isoformat() if raw_expense.expense_date else None,
            'created_at': raw_expense.created_at.isoformat() if raw_expense.created_at else None
        }
        
        # Get effective view using precedence engine
        effective_view = precedence_engine.get_effective_view(
            user_id=user_id_hash,
            tx_id=tx_id,
            raw_expense=raw_data
        )
        
        # Build audit response
        audit_data = {
            'transaction_id': tx_id,
            'user_id_hash': user_id_hash[:8] + '...',  # Partial hash for privacy
            
            'original': {
                'amount': raw_data['amount'],
                'category': raw_data['category'],
                'subcategory': raw_data['subcategory'],
                'merchant_text': raw_data['merchant_text'],
                'note': raw_data['note'],
                'expense_date': raw_data['expense_date']
            },
            
            'corrected': {
                'amount': effective_view.amount,
                'category': effective_view.category,
                'subcategory': effective_view.subcategory,
                'merchant_text': effective_view.merchant_text,
                'note': effective_view.note,
                'expense_date': raw_data['expense_date']  # Date doesn't change
            },
            
            'audit_trail': {
                'source': effective_view.source,
                'has_correction': effective_view.source == 'correction',
                'has_rule': effective_view.source == 'rule',
                'is_raw': effective_view.source == 'raw'
            },
            
            'why': _get_change_reason(user_id_hash, tx_id, effective_view.source),
            
            'ui_audit': {
                'original': f"{raw_data.get('merchant_text', 'Expense')} {raw_data['amount']} ({raw_data['category']})",
                'corrected': f"{effective_view.category} (your view)" if effective_view.source != 'raw' else "Same as original",
                'why': _get_change_reason(user_id_hash, tx_id, effective_view.source)
            }
        }
        
        # Cache the result
        set_cache_result(user_id_hash, tx_id, audit_data)
        
        # Add performance metrics
        response_time_ms = (time.time() - start_time) * 1000
        audit_data['performance'] = {
            'response_time_ms': response_time_ms,
            'cached': False
        }
        
        return jsonify(audit_data)
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve audit data',
            'message': str(e)
        }), 500

@audit_api.route('/transactions/<tx_id>/compare', methods=['GET'])
def compare_transaction_views(tx_id):
    """
    Simplified comparison endpoint for chat UI
    Returns compact format suitable for Messenger (< 280 chars)
    """
    if not pca_feature_flags.should_show_audit_ui():
        return jsonify({'error': 'Audit UI not enabled'}), 404
    
    user_id = request.args.get('user_id', 'anonymous')
    user_id_hash = ensure_hashed(user_id)
    
    try:
        # Get raw expense
        raw_expense = db.session.query(Expense).filter_by(
            transaction_id=tx_id
        ).first()
        
        if not raw_expense:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Get effective view
        raw_data = {
            'amount': float(raw_expense.amount) if raw_expense.amount else 0,
            'category': raw_expense.category,
            'merchant_text': raw_expense.merchant_text
        }
        
        effective_view = precedence_engine.get_effective_view(
            user_id=user_id_hash,
            tx_id=tx_id,
            raw_expense=raw_data
        )
        
        # Build compact response for chat
        if effective_view.source == 'raw':
            chat_format = f"✓ {raw_expense.merchant_text or 'Expense'}: ৳{raw_data['amount']}\nCategory: {raw_data['category']}"
        else:
            chat_format = f"✓ Logged: ৳{raw_data['amount']}\nOriginal: {raw_data['category']}\nYour view: {effective_view.category}"
        
        # Ensure under 280 chars
        if len(chat_format) > 250:
            chat_format = chat_format[:247] + "..."
        
        return jsonify({
            'chat_format': chat_format,
            'length': len(chat_format),
            'fits_messenger': len(chat_format) <= 280
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _get_change_reason(user_id_hash, tx_id, source):
    """Get human-readable reason for change"""
    if source == 'correction':
        correction = db.session.query(UserCorrection).filter_by(
            user_id=user_id_hash,
            transaction_id=tx_id
        ).first()
        if correction:
            return f"User correction applied on {correction.created_at.strftime('%b %d')}"
    
    elif source == 'rule':
        # Would fetch matching rule details
        return "Automatic rule applied"
    
    elif source == 'effective':
        return "AI categorization applied"
    
    return "Original transaction"

@audit_api.route('/health', methods=['GET'])
def audit_health():
    """Health check for audit API"""
    return jsonify({
        'status': 'healthy',
        'audit_ui_enabled': pca_feature_flags.should_show_audit_ui(),
        'cache_size': len(_audit_cache),
        'pca_mode': pca_feature_flags.mode
    })