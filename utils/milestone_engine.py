"""
Milestone Engine - User Gamification System
Handles streak-3 and 10-logs milestone nudges
User-visible encouragement with daily cap enforcement
"""

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, Optional

from db_base import db
from models import User
from utils.timezone_helpers import today_local

logger = logging.getLogger(__name__)

class MilestoneEngine:
    """
    Handles milestone gamification: streak-3 and 10-logs nudges
    
    Guardrails:
    - User-visible nudges only
    - Daily cap (max 1 milestone per local day)
    - Independent from analytics system
    - Uses Asia/Dhaka timezone for streak calculations
    - Never reads d1_logged or d3_completed flags
    """
    
    def __init__(self):
        self.feature_enabled = os.getenv('FEATURE_MILESTONES_SIMPLE', 'true').lower() == 'true'
        logger.info(f"Milestone Engine initialized: enabled={self.feature_enabled}")
    
    def update_streak_on_expense(self, user: User, expense_date: date) -> int:
        """
        Update consecutive day streak when expense is logged
        
        Args:
            user: User object
            expense_date: Date of expense (local date)
            
        Returns:
            int: Updated consecutive days count
        """
        if not self.feature_enabled:
            return user.consecutive_days
            
        try:
            last_log_date = user.last_log_date
            
            if last_log_date is None:
                # First ever expense log
                user.consecutive_days = 1
                user.last_log_date = expense_date
                db.session.commit()
                logger.debug(f"First expense logged for user {user.user_id_hash[:8]}... (streak: 1)")
                return 1
            
            if expense_date == last_log_date:
                # Same day, no change to streak
                return user.consecutive_days
            
            days_diff = (expense_date - last_log_date).days
            
            if days_diff == 1:
                # Consecutive day - increment streak
                user.consecutive_days += 1
                user.last_log_date = expense_date
                db.session.commit()
                logger.debug(f"Streak extended for user {user.user_id_hash[:8]}... (streak: {user.consecutive_days})")
                return user.consecutive_days
            
            elif days_diff > 1:
                # Gap detected - reset streak to 1
                user.consecutive_days = 1
                user.last_log_date = expense_date
                db.session.commit()
                logger.debug(f"Streak reset for user {user.user_id_hash[:8]}... (gap: {days_diff} days)")
                return 1
            
            else:
                # Past date (days_diff < 0) - should not happen in normal flow
                logger.warning(f"Past date expense for user {user.user_id_hash[:8]}...: {expense_date} vs {last_log_date}")
                return user.consecutive_days
                
        except Exception as e:
            logger.error(f"Streak update failed for user {user.user_id_hash[:8]}: {e}")
            return user.consecutive_days or 0
    
    def check_streak_milestone(self, user: User) -> str | None:
        """
        Check if streak-3 milestone should fire
        
        Args:
            user: User object
            
        Returns:
            str: Milestone message if fired, None otherwise
        """
        if not self.feature_enabled:
            return None
            
        try:
            # Check if user has exactly 3 consecutive days (crossing boundary)
            if user.consecutive_days == 3:
                # Check daily cap
                if self._can_fire_milestone_today(user):
                    message = self._generate_streak_3_message(user)
                    self._record_milestone_fired(user, "streak-3")
                    
                    # Emit milestone telemetry
                    self._emit_milestone_event("streak-3", user.user_id_hash, {
                        "consecutive_days": user.consecutive_days,
                        "last_log_date": user.last_log_date.isoformat() if user.last_log_date else None
                    })
                    
                    logger.info(f"Streak-3 milestone fired for user {user.user_id_hash[:8]}...")
                    return message
                else:
                    logger.debug(f"Streak-3 milestone suppressed by daily cap for user {user.user_id_hash[:8]}...")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Streak milestone check failed for user {user.user_id_hash[:8]}: {e}")
            return None
    
    def check_10logs_milestone(self, user: User) -> str | None:
        """
        Check if 10-logs milestone should fire
        
        Args:
            user: User object
            
        Returns:
            str: Milestone message if fired, None otherwise
        """
        if not self.feature_enabled:
            return None
            
        try:
            # Check if user has exactly 10 expenses (crossing boundary)
            if user.expense_count == 10:
                # Check daily cap
                if self._can_fire_milestone_today(user):
                    message = self._generate_10logs_message(user)
                    self._record_milestone_fired(user, "10-logs")
                    
                    # Emit milestone telemetry
                    self._emit_milestone_event("10-logs", user.user_id_hash, {
                        "expense_count": user.expense_count,
                        "total_amount": float(user.total_expenses) if user.total_expenses else 0
                    })
                    
                    logger.info(f"10-logs milestone fired for user {user.user_id_hash[:8]}...")
                    return message
                else:
                    logger.debug(f"10-logs milestone suppressed by daily cap for user {user.user_id_hash[:8]}...")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"10-logs milestone check failed for user {user.user_id_hash[:8]}: {e}")
            return None
    
    def check_all_milestones(self, user: User) -> str | None:
        """
        Check all milestones and return first that fires (daily cap enforcement)
        
        Args:
            user: User object
            
        Returns:
            str: Milestone message if any fired, None otherwise
        """
        if not self.feature_enabled:
            return None
        
        # Check streak milestone first (more frequent)
        streak_message = self.check_streak_milestone(user)
        if streak_message:
            return streak_message
        
        # Then check 10-logs milestone
        logs_message = self.check_10logs_milestone(user)
        if logs_message:
            return logs_message
        
        return None
    
    def _can_fire_milestone_today(self, user: User) -> bool:
        """
        Check if user can receive milestone today (daily cap)
        
        Args:
            user: User object
            
        Returns:
            bool: True if can fire milestone today
        """
        try:
            today = today_local()
            return user.last_milestone_date != today
            
        except Exception as e:
            logger.error(f"Daily cap check failed for user {user.user_id_hash[:8]}: {e}")
            return False
    
    def _record_milestone_fired(self, user: User, milestone_type: str) -> None:
        """
        Record that milestone was fired today
        
        Args:
            user: User object
            milestone_type: Type of milestone fired
        """
        try:
            user.last_milestone_date = today_local()
            db.session.commit()
            logger.debug(f"Milestone {milestone_type} recorded for user {user.user_id_hash[:8]}...")
            
        except Exception as e:
            logger.error(f"Milestone recording failed for user {user.user_id_hash[:8]}: {e}")
    
    def _generate_streak_3_message(self, user: User) -> str:
        """Generate streak-3 milestone message"""
        return (
            "🔥 Amazing! You've logged expenses for 3 days in a row! "
            "You're building a great tracking habit. Keep it up!"
        )
    
    def _generate_10logs_message(self, user: User) -> str:
        """Generate 10-logs milestone message"""
        return (
            "🎉 Congratulations! You've logged your 10th expense! "
            "You're really getting the hang of tracking your spending. Fantastic progress!"
        )
    
    def _emit_milestone_event(self, milestone_type: str, user_id_hash: str, data: dict[str, Any]) -> None:
        """
        Emit milestone telemetry event
        
        Args:
            milestone_type: Type of milestone (streak-3, 10-logs)
            user_id_hash: User identifier
            data: Event data
        """
        try:
            # Build telemetry payload
            telemetry = {
                "type": "milestone_telemetry",
                "event": "milestone_fired",
                "milestone_type": milestone_type,
                "user_id_hash": user_id_hash[:8] + "...",  # Truncated for privacy
                "timestamp": datetime.utcnow().isoformat(),
                "data": data
            }
            
            # Emit to structured logging
            logger.info(f"MILESTONE_TELEMETRY: {json.dumps(telemetry)}")
            
            # Additional logging for monitoring
            from utils.structured import log_milestone_event
            log_milestone_event(milestone_type, user_id_hash, data)
            
        except Exception as e:
            logger.error(f"Milestone telemetry emission failed for {milestone_type}: {e}")
    
    def get_milestone_status(self, user: User) -> dict[str, Any]:
        """
        Get current milestone status for user (for debugging/monitoring)
        
        Args:
            user: User object
            
        Returns:
            dict: Milestone status summary
        """
        if not self.feature_enabled:
            return {"enabled": False}
            
        try:
            today = today_local()
            can_fire_today = self._can_fire_milestone_today(user)
            
            return {
                "enabled": True,
                "consecutive_days": user.consecutive_days,
                "expense_count": user.expense_count,
                "last_log_date": user.last_log_date.isoformat() if user.last_log_date else None,
                "last_milestone_date": user.last_milestone_date.isoformat() if user.last_milestone_date else None,
                "can_fire_today": can_fire_today,
                "next_streak_milestone": max(0, 3 - user.consecutive_days),
                "next_logs_milestone": max(0, 10 - user.expense_count)
            }
            
        except Exception as e:
            logger.error(f"Milestone status failed for user {user.user_id_hash[:8]}: {e}")
            return {"enabled": True, "error": str(e)}

# Global milestone engine instance
milestone_engine = MilestoneEngine()

# Convenience functions for easy integration
def update_user_streak(user: User, expense_date: date) -> int:
    """Update user streak on expense logging"""
    return milestone_engine.update_streak_on_expense(user, expense_date)

def check_milestone_nudges(user: User) -> str | None:
    """Check all milestones and return message if any fire"""
    return milestone_engine.check_all_milestones(user)

def get_milestone_status(user: User) -> dict[str, Any]:
    """Get milestone status for user"""
    return milestone_engine.get_milestone_status(user)