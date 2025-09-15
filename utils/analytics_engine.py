"""
Analytics Engine - Block 4 Growth Metrics
Handles D1/D3 activation tracking and report counting
Silent data collection with no user-visible outputs
"""

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from models import User
from db_base import db
from utils.timezone_helpers import is_same_local_day, is_within_hours
import json

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """
    Handles Block 4 analytics: D1/D3 activation and report counting
    
    Guardrails:
    - Analytics-only (no user-visible messages)
    - One-time boolean transitions
    - Independent from milestone system
    - Uses Asia/Dhaka timezone for day calculations
    """
    
    def __init__(self):
        self.feature_enabled = os.getenv('FEATURE_ANALYTICS_BLOCK4', 'true').lower() == 'true'
        logger.info(f"Analytics Engine initialized: enabled={self.feature_enabled}")
    
    def check_d1_activation(self, user: User, expense_time: datetime) -> bool:
        """
        Check and mark D1 activation (first expense on same local day as signup)
        
        Args:
            user: User object
            expense_time: When expense was logged
            
        Returns:
            bool: True if D1 was activated (first time), False otherwise
        """
        if not self.feature_enabled:
            return False
            
        try:
            # Guard: Only process if not already activated
            if user.d1_logged:
                return False
            
            # Check if expense is on same local day as signup
            if is_same_local_day(user.created_at, expense_time):
                user.d1_logged = True
                db.session.commit()
                
                # Emit analytics telemetry
                self._emit_analytics_event("activation_d1", user.user_id_hash, {
                    "signup_source": user.signup_source,
                    "signup_time": user.created_at.isoformat(),
                    "first_expense_time": expense_time.isoformat()
                })
                
                logger.info(f"D1 activation fired for user {user.user_id_hash[:8]}...")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"D1 activation check failed for user {user.user_id_hash[:8]}: {e}")
            return False
    
    def check_d3_completion(self, user: User) -> bool:
        """
        Check and mark D3 completion (3+ expenses within 72h of signup)
        
        Args:
            user: User object
            
        Returns:
            bool: True if D3 was completed (first time), False otherwise
        """
        if not self.feature_enabled:
            return False
            
        try:
            # Guard: Only process if not already completed
            if user.d3_completed:
                return False
            
            # Check if user has 3+ expenses within 72h of signup
            current_time = datetime.utcnow()
            within_72h = is_within_hours(user.created_at, current_time, 72)
            has_enough_expenses = user.expense_count >= 3
            
            if within_72h and has_enough_expenses:
                user.d3_completed = True
                db.session.commit()
                
                # Calculate completion metrics
                signup_to_completion_hours = (current_time - user.created_at).total_seconds() / 3600
                
                # Emit analytics telemetry
                self._emit_analytics_event("activation_d3", user.user_id_hash, {
                    "signup_source": user.signup_source,
                    "signup_time": user.created_at.isoformat(),
                    "completion_time": current_time.isoformat(),
                    "hours_to_complete": round(signup_to_completion_hours, 2),
                    "expense_count": user.expense_count
                })
                
                logger.info(f"D3 completion fired for user {user.user_id_hash[:8]}...")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"D3 completion check failed for user {user.user_id_hash[:8]}: {e}")
            return False
    
    def increment_report_count(self, user: User, report_source: str = "user_command") -> bool:
        """
        Increment report request counter
        
        Args:
            user: User object
            report_source: Source of report request
            
        Returns:
            bool: True if incremented successfully
        """
        if not self.feature_enabled:
            return False
            
        try:
            user.reports_requested += 1
            db.session.commit()
            
            # Emit analytics telemetry
            self._emit_analytics_event("report_requested", user.user_id_hash, {
                "report_source": report_source,
                "total_reports": user.reports_requested,
                "user_age_days": (datetime.utcnow() - user.created_at).days
            })
            
            logger.debug(f"Report count incremented for user {user.user_id_hash[:8]}... (total: {user.reports_requested})")
            return True
            
        except Exception as e:
            logger.error(f"Report count increment failed for user {user.user_id_hash[:8]}: {e}")
            return False
    
    def set_signup_source(self, user: User, source: str) -> bool:
        """
        Set signup source if not already set
        
        Args:
            user: User object
            source: Signup source (fb-ad|organic|referral|other)
            
        Returns:
            bool: True if set successfully
        """
        if not self.feature_enabled:
            return False
            
        try:
            # Only set if currently default value
            if user.signup_source == 'other' and source != 'other':
                valid_sources = ['fb-ad', 'organic', 'referral', 'other']
                if source in valid_sources:
                    user.signup_source = source
                    db.session.commit()
                    logger.info(f"Signup source set to {source} for user {user.user_id_hash[:8]}...")
                    return True
                else:
                    logger.warning(f"Invalid signup source: {source}")
            
            return False
            
        except Exception as e:
            logger.error(f"Signup source setting failed for user {user.user_id_hash[:8]}: {e}")
            return False
    
    def get_analytics_summary(self, user: User) -> Dict[str, Any]:
        """
        Get current analytics state for user (for debugging/monitoring)
        
        Args:
            user: User object
            
        Returns:
            dict: Analytics summary
        """
        if not self.feature_enabled:
            return {"enabled": False}
            
        try:
            return {
                "enabled": True,
                "signup_source": user.signup_source,
                "d1_logged": user.d1_logged,
                "d3_completed": user.d3_completed,
                "reports_requested": user.reports_requested,
                "expense_count": user.expense_count,
                "user_age_hours": (datetime.utcnow() - user.created_at).total_seconds() / 3600
            }
            
        except Exception as e:
            logger.error(f"Analytics summary failed for user {user.user_id_hash[:8]}: {e}")
            return {"enabled": True, "error": str(e)}
    
    def _emit_analytics_event(self, event_name: str, user_id_hash: str, data: Dict[str, Any]) -> None:
        """
        Emit analytics telemetry event
        
        Args:
            event_name: Event name (activation_d1, activation_d3, report_requested)
            user_id_hash: User identifier
            data: Event data
        """
        try:
            # Build telemetry payload
            telemetry = {
                "type": "analytics_telemetry",
                "event": event_name,
                "user_id_hash": user_id_hash[:8] + "...",  # Truncated for privacy
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }
            
            # Emit to structured logging
            logger.info(f"ANALYTICS_TELEMETRY: {json.dumps(telemetry)}")
            
            # Additional logging for monitoring
            from utils.structured import log_analytics_event
            log_analytics_event(event_name, user_id_hash, data)
            
        except Exception as e:
            logger.error(f"Analytics telemetry emission failed for {event_name}: {e}")

# Global analytics engine instance
analytics_engine = AnalyticsEngine()

# Convenience functions for easy integration
def track_d1_activation(user: User, expense_time: datetime) -> bool:
    """Track D1 activation for expense logging"""
    return analytics_engine.check_d1_activation(user, expense_time)

def track_d3_completion(user: User) -> bool:
    """Track D3 completion for expense logging"""
    return analytics_engine.check_d3_completion(user)

def track_report_request(user: User, source: str = "user_command") -> bool:
    """Track report request for report generation"""
    return analytics_engine.increment_report_count(user, source)

def set_user_signup_source(user: User, source: str) -> bool:
    """Set user signup source if available"""
    return analytics_engine.set_signup_source(user, source)

def get_user_analytics(user: User) -> Dict[str, Any]:
    """Get analytics summary for user"""
    return analytics_engine.get_analytics_summary(user)