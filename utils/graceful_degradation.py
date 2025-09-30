"""
Graceful Degradation Helpers
Provides "oops state" responses when features are disabled via kill switches
"""

from flask import jsonify, render_template_string, Response, make_response
from typing import Tuple, Union
import functools

# === OOPS STATE HTML TEMPLATES ===

OOPS_BANNER_HTML = """
<div class="alert alert-info" role="alert" style="margin: 1rem 0;">
    <i class="fas fa-info-circle"></i>
    <span>Smart suggestions are taking a quick break. Your expense tracking works perfectly!</span>
</div>
"""

OOPS_INSIGHTS_HTML = """
<div class="card" style="margin: 1rem 0; padding: 2rem; text-align: center;">
    <i class="fas fa-chart-line" style="font-size: 3rem; color: #6c757d; margin-bottom: 1rem;"></i>
    <h3>Insights Temporarily Unavailable</h3>
    <p class="text-muted">We're giving our insights system a quick refresh. Your data is safe and all expense tracking features work normally.</p>
    <p class="text-muted"><small>Check back in a few minutes!</small></p>
</div>
"""

OOPS_EXPORTS_HTML = """
<div class="card" style="margin: 1rem 0; padding: 2rem; text-align: center;">
    <i class="fas fa-download" style="font-size: 3rem; color: #6c757d; margin-bottom: 1rem;"></i>
    <h3>Exports Temporarily Unavailable</h3>
    <p class="text-muted">Data export is taking a quick break. Your expenses are safely stored and you can view them anytime.</p>
    <p class="text-muted"><small>Try again in a few minutes!</small></p>
</div>
"""

# === GRACEFUL DEGRADATION HELPERS ===

def oops_banner_response() -> str:
    """Return graceful HTML when banners are disabled"""
    return OOPS_BANNER_HTML

def oops_insights_response() -> Tuple[str, int]:
    """Return graceful HTML response when insights are disabled"""
    return OOPS_INSIGHTS_HTML, 200

def oops_exports_response() -> Tuple[Response, int]:
    """Return graceful JSON response when exports are disabled"""
    response = make_response(jsonify({
        "error": "exports_unavailable",
        "message": "Data export is temporarily unavailable. Your data is safe and can be viewed in the app.",
        "user_friendly_message": "Exports are taking a quick break. Try again in a few minutes!",
        "retry_after_seconds": 300  # 5 minutes
    }), 503)
    
    # Add Retry-After header for proper HTTP semantics
    response.headers['Retry-After'] = '300'
    return response, 503

def oops_insights_json_response() -> Tuple[Response, int]:
    """Return graceful JSON response when insights API is disabled"""
    return jsonify({
        "error": "insights_unavailable",
        "message": "Insights are temporarily unavailable",
        "user_friendly_message": "We're refreshing our insights. Check back soon!",
        "data": {
            "total_expenses": 0,
            "placeholder": True,
            "message": "Insights temporarily unavailable"
        }
    }), 200  # 200 to avoid breaking the UI

def should_show_empty_state(feature: str) -> bool:
    """
    Check if we should show empty/oops state for a feature.
    Used for silent degradation without user notification.
    
    Args:
        feature: "banners", "insights", or "exports"
        
    Returns:
        True if feature is disabled and should show oops state
    """
    from utils.feature_flags import can_use_banners, can_use_insights, can_use_exports
    
    feature_checks = {
        "banners": can_use_banners,
        "insights": can_use_insights,
        "exports": can_use_exports
    }
    
    check_func = feature_checks.get(feature)
    if check_func is None:
        return False
    
    return not check_func()

# === DECORATOR FOR GRACEFUL DEGRADATION ===

def graceful_feature(feature_type: str):
    """
    Decorator to handle graceful degradation for features.
    
    Usage:
        @graceful_feature('insights')
        def get_insights():
            return insights_data
    
    Args:
        feature_type: "banners", "insights", or "exports"
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if should_show_empty_state(feature_type):
                if feature_type == "banners":
                    return oops_banner_response()
                elif feature_type == "insights":
                    # Check if route expects JSON or HTML
                    from flask import request
                    
                    # Better JSON detection: check request.is_json or HX-Request header
                    if request.is_json or 'HX-Request' not in request.headers:
                        return oops_insights_json_response()
                    return oops_insights_response()
                elif feature_type == "exports":
                    return oops_exports_response()
            
            # Feature is enabled, call the actual function
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
