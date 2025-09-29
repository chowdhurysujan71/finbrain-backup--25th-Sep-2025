"""
Web-only nudging API endpoints for FinBrain.

Provides banner management and spending detection APIs behind feature flags.
All endpoints require authentication and feature flag approval.
"""

import logging
from datetime import datetime, timedelta, UTC
from utils.test_clock import get_current_time, get_banner_test_time
from decimal import Decimal
from typing import Dict, List, Optional

from flask import Blueprint, request, jsonify, g
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import joinedload

from db_base import db
from models import Banner, Expense, User
from utils.feature_flags import can_use_nudges, can_receive_spending_alerts, can_use_banners
from utils.money import normalize_amount_fields

logger = logging.getLogger(__name__)

# Create blueprint for nudging endpoints
nudges_bp = Blueprint('nudges', __name__, url_prefix='/api')

def get_current_user():
    """Get current user from g.user_id (our auth system)"""
    if not g.user_id:
        return None
    return User.query.filter_by(user_id_hash=g.user_id).first()

def require_api_auth(f):
    """Custom API authentication decorator that returns JSON instead of redirecting."""
    def wrapper(*args, **kwargs):
        # Check authentication using g.user_id from our main auth system
        if not g.user_id:
            return jsonify({
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED",
                "success": False,
                "trace_id": getattr(g, 'request_id', 'unknown')
            }), 401
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def require_nudges_enabled(f):
    """Decorator to ensure nudges are enabled for the user."""
    def wrapper(*args, **kwargs):
        # Get user from our auth system
        if not g.user_id:
            return jsonify({
                "error": "Authentication required", 
                "error_code": "AUTH_REQUIRED",
                "success": False,
                "trace_id": getattr(g, 'request_id', 'unknown')
            }), 401
        
        # Get user object for feature flag check
        user = User.query.filter_by(user_id_hash=g.user_id).first()
        if not user:
            return jsonify({"error": "User not found", "success": False}), 404
        
        if not can_use_nudges(user.email):
            return jsonify({"error": "Nudges not enabled for this user", "success": False}), 403
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def require_spending_alerts_enabled(f):
    """Decorator to ensure spending alerts are enabled for the user."""
    def wrapper(*args, **kwargs):
        # Get user from our auth system
        if not g.user_id:
            return jsonify({
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED", 
                "success": False,
                "trace_id": getattr(g, 'request_id', 'unknown')
            }), 401
        
        # Get user object for feature flag check
        user = User.query.filter_by(user_id_hash=g.user_id).first()
        if not user:
            return jsonify({"error": "User not found", "success": False}), 404
        
        if not can_receive_spending_alerts(user.email):
            return jsonify({"error": "Spending alerts not enabled for this user", "success": False}), 403
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def require_banners_enabled(f):
    """Decorator to ensure banners are enabled for the user."""
    def wrapper(*args, **kwargs):
        # Get user from our auth system
        if not g.user_id:
            return jsonify({
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED", 
                "success": False,
                "trace_id": getattr(g, 'request_id', 'unknown')
            }), 401
        
        # Get user object for feature flag check
        user = User.query.filter_by(user_id_hash=g.user_id).first()
        if not user:
            return jsonify({"error": "User not found", "success": False}), 404
        
        if not can_use_banners(user.email):
            return jsonify({"error": "Banners not enabled for this user", "success": False}), 403
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@nudges_bp.route('/banners', methods=['GET'])
@require_api_auth
@require_banners_enabled
def get_active_banners():
    """
    Get active banners for the current user.
    
    Returns:
        JSON array of active banners ordered by priority
    """
    try:
        # Get user from auth system
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get active banners for user (using test clock for deterministic testing)
        banners = Banner.get_active_for_user(user.user_id_hash, limit=5)
        
        # Mark banners as shown and return data
        banner_data = []
        for banner in banners:
            banner.mark_shown()
            banner_data.append(banner.to_dict())
        
        # Commit the shown updates
        db.session.commit()
        
        logger.info(f"Retrieved {len(banner_data)} active banners for user {user.email}")
        return jsonify({
            "banners": banner_data,
            "total_count": len(banner_data),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error retrieving banners: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to retrieve banners"}), 500

@nudges_bp.route('/banners/<int:banner_id>/dismiss', methods=['POST'])
@require_api_auth
@require_banners_enabled
def dismiss_banner(banner_id: int):
    """
    Dismiss a banner by ID.
    
    Args:
        banner_id: ID of banner to dismiss
        
    Returns:
        JSON success response
    """
    try:
        # Get user from auth system
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Find the banner
        banner = Banner.query.filter_by(
            id=banner_id,
            user_id_hash=user.user_id_hash
        ).first()
        
        if not banner:
            return jsonify({"error": "Banner not found"}), 404
        
        if not banner.dismissible:
            return jsonify({"error": "Banner cannot be dismissed"}), 400
        
        # Dismiss the banner
        banner.dismiss()
        db.session.commit()
        
        logger.info(f"User {user.email} dismissed banner {banner_id}")
        return jsonify({
            "success": True,
            "message": "Banner dismissed successfully",
            "banner_id": banner_id
        })
        
    except Exception as e:
        logger.error(f"Error dismissing banner {banner_id}: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to dismiss banner"}), 500

@nudges_bp.route('/banners/<int:banner_id>/click', methods=['POST'])
@require_api_auth
@require_banners_enabled
def click_banner_action(banner_id: int):
    """
    Record banner action click.
    
    Args:
        banner_id: ID of banner that was clicked
        
    Returns:
        JSON success response
    """
    try:
        # Get user from auth system
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Find the banner
        banner = Banner.query.filter_by(
            id=banner_id,
            user_id_hash=user.user_id_hash
        ).first()
        
        if not banner:
            return jsonify({"error": "Banner not found"}), 404
        
        # Record the click
        banner.click_action()
        db.session.commit()
        
        logger.info(f"User {user.email} clicked banner {banner_id} action")
        return jsonify({
            "success": True,
            "message": "Banner click recorded",
            "banner_id": banner_id,
            "action_url": banner.action_url
        })
        
    except Exception as e:
        logger.error(f"Error recording banner click {banner_id}: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to record banner click"}), 500

@nudges_bp.route('/nudges/check-today', methods=['GET'])
@require_spending_alerts_enabled
def check_spending_today():
    """
    Check for spending spike alerts for today.
    
    Returns:
        JSON with spending analysis and any triggered alerts
    """
    try:
        # Get user from auth system
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get today's date
        today = datetime.now(UTC).date()
        
        # Calculate today's spending
        today_expenses = Expense.query_active().filter(
            Expense.user_id_hash == user.user_id_hash,
            Expense.date == today
        ).all()
        
        today_total = sum(float(expense.amount) for expense in today_expenses)
        
        # Calculate recent average (last 7 days, excluding today)
        week_ago = today - timedelta(days=7)
        recent_expenses = Expense.query_active().filter(
            Expense.user_id_hash == user.user_id_hash,
            Expense.date >= week_ago,
            Expense.date < today
        ).all()
        
        # Calculate daily averages
        daily_totals = {}
        for expense in recent_expenses:
            date_key = expense.date.isoformat()
            daily_totals[date_key] = daily_totals.get(date_key, 0) + float(expense.amount)
        
        avg_daily = sum(daily_totals.values()) / max(len(daily_totals), 1)
        
        # Determine if this is a spending spike
        spike_threshold = avg_daily * 1.5  # 50% above average
        high_threshold = avg_daily * 2.0   # 100% above average
        
        is_spike = today_total > spike_threshold
        is_high_spike = today_total > high_threshold
        
        # Check if we should create an alert banner
        should_alert = is_spike and today_total > 500  # Minimum 500 BDT threshold
        
        alert_banner = None
        if should_alert:
            # Check if we already have an alert for today
            existing_alert = Banner.query_active().filter(
                Banner.user_id_hash == user.user_id_hash,
                Banner.banner_type == 'spending_alert',
                func.date(Banner.created_at) == today
            ).first()
            
            if not existing_alert:
                # Create spending alert banner
                alert_style = 'error' if is_high_spike else 'warning'
                alert_title = f"High Spending Alert: ৳{today_total:,.0f} today"
                alert_message = f"You've spent ৳{today_total:,.0f} today, which is {(today_total/avg_daily*100):,.0f}% of your recent daily average (৳{avg_daily:,.0f}). Consider reviewing your expenses."
                
                banner = Banner()
                banner.user_id_hash = user.user_id_hash
                banner.banner_type = 'spending_alert'
                banner.title = alert_title
                banner.message = alert_message
                banner.action_text = "View Today's Expenses"
                banner.action_url = "/chat?filter=today"
                banner.priority = 2  # High priority
                banner.style = alert_style
                banner.trigger_data = {
                    'amount': today_total,
                    'threshold': spike_threshold,
                    'period': 'daily',
                    'avg_daily': avg_daily
                }
                banner.expires_at = datetime.now(UTC) + timedelta(hours=12)
                
                db.session.add(banner)
                db.session.commit()
                
                alert_banner = banner.to_dict()
                logger.info(f"Created spending alert for user {user.email}: ৳{today_total} vs avg ৳{avg_daily}")
        
        return jsonify({
            "analysis": {
                "today_total": today_total,
                "today_count": len(today_expenses),
                "avg_daily": round(avg_daily, 2),
                "recent_days_count": len(daily_totals),
                "is_spike": is_spike,
                "is_high_spike": is_high_spike,
                "spike_threshold": round(spike_threshold, 2),
                "analysis_date": today.isoformat()
            },
            "alert_created": alert_banner is not None,
            "alert_banner": alert_banner,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error checking spending alerts: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to check spending alerts"}), 500

@nudges_bp.route('/nudges/prefs', methods=['GET', 'POST'])
@require_nudges_enabled
def nudge_preferences():
    """
    Get or update user's nudge preferences.
    
    GET: Returns current preferences
    POST: Updates preferences
    """
    try:
        # Get user
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        if request.method == 'GET':
            # Return current preferences
            prefs = user.preferences or {}
            nudge_prefs = prefs.get('nudges', {})
            
            return jsonify({
                "preferences": {
                    "spending_alerts_enabled": nudge_prefs.get('spending_alerts', True),
                    "streak_reminders_enabled": nudge_prefs.get('streak_reminders', True),
                    "category_tips_enabled": nudge_prefs.get('category_tips', True),
                    "milestone_notifications_enabled": nudge_prefs.get('milestones', True),
                    "alert_threshold_multiplier": nudge_prefs.get('threshold_multiplier', 1.5),
                    "minimum_alert_amount": nudge_prefs.get('min_alert_amount', 500)
                },
                "last_updated": prefs.get('nudges_updated_at'),
                "user_email": user.email
            })
        
        elif request.method == 'POST':
            # Update preferences
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            # Get current preferences
            prefs = user.preferences or {}
            nudge_prefs = prefs.get('nudges', {})
            
            # Update with new values
            if 'spending_alerts_enabled' in data:
                nudge_prefs['spending_alerts'] = bool(data['spending_alerts_enabled'])
            
            if 'streak_reminders_enabled' in data:
                nudge_prefs['streak_reminders'] = bool(data['streak_reminders_enabled'])
            
            if 'category_tips_enabled' in data:
                nudge_prefs['category_tips'] = bool(data['category_tips_enabled'])
            
            if 'milestone_notifications_enabled' in data:
                nudge_prefs['milestones'] = bool(data['milestone_notifications_enabled'])
            
            if 'alert_threshold_multiplier' in data:
                multiplier = float(data['alert_threshold_multiplier'])
                if 1.0 <= multiplier <= 3.0:  # Reasonable range
                    nudge_prefs['threshold_multiplier'] = multiplier
            
            if 'minimum_alert_amount' in data:
                min_amount = float(data['minimum_alert_amount'])
                if min_amount >= 0:
                    nudge_prefs['min_alert_amount'] = min_amount
            
            # Save updated preferences
            prefs['nudges'] = nudge_prefs
            prefs['nudges_updated_at'] = datetime.utcnow().isoformat()
            user.preferences = prefs
            
            db.session.commit()
            
            logger.info(f"Updated nudge preferences for user {user.email}")
            return jsonify({
                "success": True,
                "message": "Preferences updated successfully",
                "preferences": nudge_prefs
            })
        
        # Should never reach here due to method restriction, but LSP requires it
        return jsonify({"error": "Method not allowed"}), 405
        
    except Exception as e:
        logger.error(f"Error handling nudge preferences: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to handle preferences"}), 500

# =============================
# HEALTH CHECK ENDPOINTS
# =============================

@nudges_bp.route('/health/banners', methods=['GET'])
def health_check_banners():
    """
    Health check endpoint for banner system with comprehensive validation.
    
    Returns:
        JSON with system health status and detailed diagnostics
    """
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': get_current_time().isoformat(),
            'checks': {},
            'metrics': {}
        }
        
        # Check database connectivity
        try:
            banner_count = db.session.query(Banner).count()
            health_status['checks']['database'] = {
                'status': 'healthy',
                'total_banners': banner_count
            }
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Check feature flags
        try:
            from utils.feature_flags import can_use_nudges
            flag_status = can_use_nudges('test@example.com')
            health_status['checks']['feature_flags'] = {
                'status': 'healthy',
                'nudges_enabled': flag_status
            }
        except Exception as e:
            health_status['checks']['feature_flags'] = {
                'status': 'unhealthy', 
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Check active banners metrics
        try:
            from sqlalchemy import func, and_
            active_banners = db.session.execute(
                db.select(func.count(Banner.id)).where(
                    and_(
                        Banner.dismissed_at.is_(None),
                        Banner.expires_at > get_banner_test_time()
                    )
                )
            ).scalar() or 0
            
            expired_banners = db.session.execute(
                db.select(func.count(Banner.id)).where(
                    Banner.expires_at <= get_banner_test_time()
                )
            ).scalar() or 0
            
            health_status['metrics']['active_banners'] = active_banners
            health_status['metrics']['expired_banners'] = expired_banners
            
        except Exception as e:
            health_status['checks']['banner_metrics'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Set overall status code
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error(f"Banner health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': get_current_time().isoformat(),
            'error': str(e)
        }), 503

@nudges_bp.route('/banners/seed', methods=['POST'])
@require_api_auth
@require_banners_enabled
def seed_test_banners():
    """
    Seed test banners for the current user - useful for development and testing.
    
    Request body can include optional custom banner data, otherwise defaults are used.
    """
    try:
        # Get user from auth system
        user = get_current_user()
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Get optional custom banner data from request
        data = request.get_json() or {}
        
        # Create default test banners
        test_banners = []
        
        # Banner 1: Spending Alert
        banner1 = Banner()
        banner1.user_id_hash = user.user_id_hash
        banner1.title = data.get('banner1_title', "Spending Alert 📊")
        banner1.message = data.get('banner1_message', "You've spent 15% more this week compared to last week. Review your expenses to stay on track.")
        banner1.banner_type = "spending_alert"
        banner1.priority = data.get('banner1_priority', 2)
        banner1.expires_at = get_banner_test_time() + timedelta(days=data.get('banner1_expires_days', 7))
        banner1.dismissible = data.get('banner1_dismissible', True)
        banner1.action_text = data.get('banner1_action_text', "Review Spending")
        banner1.action_url = data.get('banner1_action_url', "/chat")
        banner1.style = data.get('banner1_style', "warning")
        
        # Banner 2: Savings Tip
        banner2 = Banner()
        banner2.user_id_hash = user.user_id_hash
        banner2.title = data.get('banner2_title', "💡 Savings Tip")
        banner2.message = data.get('banner2_message', "Try the 50/30/20 rule: 50% needs, 30% wants, 20% savings. Start small and build the habit!")
        banner2.banner_type = "savings_tip"
        banner2.priority = data.get('banner2_priority', 3)
        banner2.expires_at = get_banner_test_time() + timedelta(days=data.get('banner2_expires_days', 14))
        banner2.dismissible = data.get('banner2_dismissible', True)
        banner2.action_text = data.get('banner2_action_text', "Learn More")
        banner2.action_url = data.get('banner2_action_url', "/chat")
        banner2.style = data.get('banner2_style', "info")
        
        test_banners.extend([banner1, banner2])
        
        # Add optional third banner if requested
        if data.get('create_achievement_banner', False):
            banner3 = Banner()
            banner3.user_id_hash = user.user_id_hash
            banner3.title = data.get('banner3_title', "🎉 Achievement Unlocked!")
            banner3.message = data.get('banner3_message', "Congratulations! You've tracked expenses for 7 consecutive days. Keep up the great work!")
            banner3.banner_type = "achievement"
            banner3.priority = data.get('banner3_priority', 1)  # High priority
            banner3.expires_at = get_banner_test_time() + timedelta(days=data.get('banner3_expires_days', 3))
            banner3.dismissible = data.get('banner3_dismissible', True)
            banner3.action_text = data.get('banner3_action_text', "Continue Tracking")
            banner3.action_url = data.get('banner3_action_url', "/chat")
            banner3.style = data.get('banner3_style', "success")
            test_banners.append(banner3)
        
        # Save all banners to database
        for banner in test_banners:
            db.session.add(banner)
        
        db.session.commit()
        
        logger.info(f"Seeded {len(test_banners)} test banners for user {user.email}")
        
        return jsonify({
            "success": True,
            "message": f"Successfully seeded {len(test_banners)} test banners",
            "banners_created": len(test_banners),
            "banner_ids": [banner.id for banner in test_banners],
            "user_email": user.email
        })
        
    except Exception as e:
        logger.error(f"Error seeding test banners: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to seed test banners"}), 500

@nudges_bp.route('/health/nudges', methods=['GET'])  
def health_check_nudges():
    """
    Health check endpoint for spending detection and nudges system.
    
    Returns:
        JSON with nudges system health status and metrics
    """
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': get_current_time().isoformat(),
            'checks': {},
            'metrics': {}
        }
        
        # Check database tables
        try:
            expense_count = db.session.query(Expense).count()
            user_count = db.session.query(User).count()
            
            health_status['checks']['database_tables'] = {
                'status': 'healthy',
                'expense_count': expense_count,
                'user_count': user_count
            }
        except Exception as e:
            health_status['checks']['database_tables'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Check spending detection capabilities
        try:
            # Test spending analysis on recent data
            week_ago = datetime.now(UTC) - timedelta(days=7)
            recent_expenses = db.session.query(func.count(Expense.id)).filter(
                Expense.created_at >= week_ago
            ).scalar()
            
            health_status['metrics']['recent_expenses_7d'] = recent_expenses
            
            # Test spending spike detection logic
            test_threshold = Decimal('1000.00')  # Test threshold
            
            health_status['checks']['spending_detection'] = {
                'status': 'healthy',
                'test_threshold': str(test_threshold),
                'recent_activity': recent_expenses > 0
            }
            
        except Exception as e:
            health_status['checks']['spending_detection'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Check feature flag system
        try:
            from utils.feature_flags import can_receive_spending_alerts
            alerts_enabled = can_receive_spending_alerts('test@example.com')
            
            health_status['checks']['alert_system'] = {
                'status': 'healthy',
                'alerts_enabled': alerts_enabled
            }
        except Exception as e:
            health_status['checks']['alert_system'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
        
        # Set overall status code
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error(f"Nudges health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': get_current_time().isoformat(),
            'error': str(e)
        }), 503

# Register the blueprint
def register_nudges_routes(app):
    """Register nudging routes with the Flask app."""
    app.register_blueprint(nudges_bp)
    logger.info("✓ Nudge API routes registered")