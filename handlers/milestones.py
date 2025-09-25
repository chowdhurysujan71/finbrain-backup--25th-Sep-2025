"""
Milestone Coaching Handler - Detects and fires achievement milestones
"""

import logging
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Optional

from utils.structured import log_structured_event

logger = logging.getLogger(__name__)

def check_milestones_after_log(user_id_hash: str) -> str | None:
    """
    Check for milestone achievements after successful expense logging
    Returns milestone message if one should be fired, None otherwise
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        
    Returns:
        Milestone message string or None
    """
    try:
        from db_base import db
        from models import UserMilestone
        
        # Check daily milestone cap (max 1 per day)
        today = date.today()
        daily_count = db.session.query(UserMilestone).filter(
            UserMilestone.user_id_hash == user_id_hash,
            UserMilestone.daily_count_date == today
        ).count()
        
        if daily_count >= 1:
            logger.debug(f"User {user_id_hash[:8]}... already reached daily milestone cap")
            return None
        
        # Check streak-3 milestone
        streak_message = _check_streak_milestone(user_id_hash)
        if streak_message:
            return streak_message
            
        # Check 10-logs milestone  
        logs_message = _check_logs_milestone(user_id_hash)
        if logs_message:
            return logs_message
            
        return None
        
    except Exception as e:
        logger.error(f"Milestone check error: {e}")
        return None

def _check_streak_milestone(user_id_hash: str) -> str | None:
    """Check if user has achieved 3-day logging streak"""
    try:
        from db_base import db
        from models import UserMilestone
        
        # Check if already fired
        existing = db.session.query(UserMilestone).filter(
            UserMilestone.user_id_hash == user_id_hash,
            UserMilestone.milestone_type == 'streak-3'
        ).first()
        
        if existing:
            return None  # Already fired once per lifetime
            
        # Calculate current streak using existing logic from report handler
        streak_days = _calculate_streak_days(user_id_hash)
        
        if streak_days >= 3:
            # Fire the milestone
            milestone = UserMilestone()
            milestone.user_id_hash = user_id_hash
            milestone.milestone_type = 'streak-3'
            milestone.fired_at = datetime.utcnow()
            milestone.daily_count_date = date.today()
            
            db.session.add(milestone)
            db.session.commit()
            
            # Log telemetry
            _log_milestone_telemetry('streak-3', user_id_hash, None, None)
            
            logger.info(f"Fired streak-3 milestone for user {user_id_hash[:8]}...")
            return "🔥 3-day streak! You're building a habit."
            
        return None
        
    except Exception as e:
        logger.error(f"Streak milestone check error: {e}")
        return None

def _check_logs_milestone(user_id_hash: str) -> str | None:
    """Check if user has reached 10 total logs"""
    try:
        from db_base import db
        from models import Expense, UserMilestone
        
        # Check if already fired
        existing = db.session.query(UserMilestone).filter(
            UserMilestone.user_id_hash == user_id_hash,
            UserMilestone.milestone_type == '10-logs'
        ).first()
        
        if existing:
            return None  # Already fired once per lifetime
            
        # Count total logs for user
        total_logs = db.session.query(Expense).filter(
            Expense.user_id_hash == user_id_hash
        ).count()
        
        if total_logs >= 10:
            # Fire the milestone
            milestone = UserMilestone()
            milestone.user_id_hash = user_id_hash
            milestone.milestone_type = '10-logs'
            milestone.fired_at = datetime.utcnow()
            milestone.daily_count_date = date.today()
            
            db.session.add(milestone)
            db.session.commit()
            
            # Log telemetry
            _log_milestone_telemetry('10-logs', user_id_hash, None, None)
            
            logger.info(f"Fired 10-logs milestone for user {user_id_hash[:8]}...")
            return "🎉 10th log! That's consistency."
            
        return None
        
    except Exception as e:
        logger.error(f"Logs milestone check error: {e}")
        return None

def _calculate_streak_days(user_id_hash: str) -> int:
    """
    Calculate consecutive logging days for user
    Reuses logic from handlers/report.py
    """
    try:
        from db_base import db
        from models import Expense
        
        # Calculate consecutive logging days
        today = datetime.now(UTC).date()
        streak_days = 0
        check_date = today
        
        for i in range(30):  # Check up to 30 days back
            expenses_on_date = db.session.query(Expense).filter(
                Expense.user_id_hash == user_id_hash,
                db.func.date(Expense.created_at) == check_date
            ).count()
            
            if expenses_on_date > 0:
                streak_days += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        return streak_days
        
    except Exception as e:
        logger.error(f"Streak calculation error: {e}")
        return 0

def _log_milestone_telemetry(milestone_type: str, user_id_hash: str, 
                           category: str | None, delta_pct: float | None):
    """Log milestone telemetry event"""
    try:
        event_data = {
            "user_id": user_id_hash,
            "type": milestone_type,
            "category": category,
            "delta_pct": delta_pct
        }
        
        log_structured_event("milestone_fired", event_data, user_id_hash)
        logger.info(f"Telemetry: milestone_fired {milestone_type} for user {user_id_hash[:8]}...")
        
    except Exception as e:
        logger.debug(f"Milestone telemetry failed: {e}")

# Roadmap items - not implemented in demo
def _check_category_spike_milestone(user_id_hash: str) -> str | None:
    """
    ROADMAP: Check for category spending spikes ≥25%
    Requires scheduled job system for end-of-day processing
    """
    # TODO: Implement when scheduled job system is available
    return None

def _check_small_win_milestone(user_id_hash: str) -> str | None:
    """
    ROADMAP: Check for category spending reductions ≥10%
    Requires scheduled job system for end-of-day processing  
    """
    # TODO: Implement when scheduled job system is available
    return None