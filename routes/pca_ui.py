"""
PCA UI Routes for Overlay System
Handles web interface for rule management and audit displays
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for
import logging
from datetime import datetime

from app import db
from models_pca import UserRule, UserCorrection
from utils.pca_feature_flags import pca_feature_flags
from utils.deterministic import ensure_hashed

logger = logging.getLogger("finbrain.pca_ui")

# Create blueprint
pca_ui = Blueprint('pca_ui', __name__)

@pca_ui.route('/rules')
def rule_manager():
    """Rule management interface"""
    if not pca_feature_flags.should_enable_rules():
        flash('Rule management is not currently enabled', 'warning')
        return redirect(url_for('index'))
    
    try:
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        # Get all user rules
        rules = db.session.query(UserRule).filter_by(user_id=user_id).order_by(
            UserRule.created_at.desc()
        ).all()
        
        # Format rules for display
        rules_data = []
        for rule in rules:
            rules_data.append({
                'id': rule.id,
                'rule_id': rule.rule_id,
                'rule_name': rule.rule_name or f'Rule #{rule.id}',
                'pattern': rule.pattern_json,
                'rule_set': rule.rule_set_json,
                'active': rule.active,
                'created_at': rule.created_at,
                'last_applied': rule.last_applied,
                'application_count': rule.application_count
            })
        
        return render_template('rule_manager.html', 
                             rules=rules_data,
                             enable_rules=True)
        
    except Exception as e:
        logger.error(f"Error in rule manager: {e}")
        flash('Error loading rules', 'danger')
        return redirect(url_for('index'))

@pca_ui.route('/transactions/<tx_id>/audit')
def transaction_audit(tx_id):
    """Show audit view for a specific transaction"""
    if not pca_feature_flags.should_show_audit_ui():
        flash('Audit view is not currently enabled', 'warning')
        return redirect(url_for('index'))
    
    try:
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        # Get original transaction (implement based on your data model)
        original = _get_original_transaction(tx_id)
        if not original:
            flash('Transaction not found', 'danger')
            return redirect(url_for('index'))
        
        # Get effective view
        from utils.precedence_engine import precedence_engine
        effective = precedence_engine.get_effective_view(
            user_id=user_id,
            tx_id=tx_id,
            raw_expense=original
        )
        
        return render_template('transaction_audit.html',
                             tx_id=tx_id,
                             original=original,
                             effective=effective.to_dict(),
                             source=effective.source,
                             enable_rules=pca_feature_flags.should_enable_rules())
        
    except Exception as e:
        logger.error(f"Error in transaction audit for {tx_id}: {e}")
        flash('Error loading transaction audit', 'danger')
        return redirect(url_for('index'))

@pca_ui.route('/dashboard/pca')
def pca_dashboard():
    """PCA system dashboard"""
    if not pca_feature_flags.is_overlay_active():
        flash('PCA overlay system is not currently active', 'warning')
        return redirect(url_for('index'))
    
    try:
        user_id = ensure_hashed("demo_user")  # Replace with actual user identification
        
        # Get user statistics
        total_rules = db.session.query(UserRule).filter_by(user_id=user_id).count()
        active_rules = db.session.query(UserRule).filter_by(user_id=user_id, active=True).count()
        total_corrections = db.session.query(UserCorrection).filter_by(user_id=user_id).count()
        
        # Get recent activity
        recent_rules = db.session.query(UserRule).filter_by(user_id=user_id).order_by(
            UserRule.created_at.desc()
        ).limit(5).all()
        
        recent_corrections = db.session.query(UserCorrection).filter_by(user_id=user_id).order_by(
            UserCorrection.created_at.desc()
        ).limit(5).all()
        
        # Get system status
        system_status = pca_feature_flags.get_status()
        
        return render_template('pca_dashboard.html',
                             total_rules=total_rules,
                             active_rules=active_rules,
                             total_corrections=total_corrections,
                             recent_rules=recent_rules,
                             recent_corrections=recent_corrections,
                             system_status=system_status)
        
    except Exception as e:
        logger.error(f"Error in PCA dashboard: {e}")
        flash('Error loading dashboard', 'danger')
        return redirect(url_for('index'))

@pca_ui.context_processor
def inject_pca_flags():
    """Inject PCA flags into template context"""
    return {
        'pca_overlay_active': pca_feature_flags.is_overlay_active(),
        'pca_show_audit': pca_feature_flags.should_show_audit_ui(),
        'pca_enable_rules': pca_feature_flags.should_enable_rules(),
        'pca_mode': pca_feature_flags.mode
    }

def _get_original_transaction(tx_id: str) -> dict:
    """Get original transaction data"""
    try:
        # This would query your expense table
        # For now, return sample data
        return {
            'tx_id': tx_id,
            'amount': 100,
            'category': 'food',
            'merchant_text': 'Sample Restaurant',
            'timestamp': datetime.now()
        }
    except Exception:
        return None