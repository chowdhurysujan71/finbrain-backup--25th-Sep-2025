"""
Block 6 - 3-Day Challenge Handler
Implements explicit 3-Day Challenge flow with policy-compliant automation
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
from app import db
from models import User
from utils.structured import log_structured_event

logger = logging.getLogger(__name__)

def handle_challenge_start(user_id_hash: str) -> Dict[str, Any]:
    """
    Handle START 3D command with idempotent challenge creation
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        
    Returns:
        Dict with response text and metadata
    """
    try:
        user = db.session.query(User).filter_by(user_id_hash=user_id_hash).first()
        if not user:
            return {
                'text': "User not found. Please send a message first to initialize your account.",
                'success': False
            }
        
        # Check if user already has an active challenge (idempotent)
        if user.challenge_active:
            days_remaining = _calculate_days_remaining(user.challenge_start_date, user.challenge_end_date)
            if days_remaining >= 0:
                return {
                    'text': f"You already have an active 3-Day Challenge! Day {3 - days_remaining}/3 in progress. Keep logging! 🎯",
                    'success': True,
                    'already_active': True
                }
        
        # Start new challenge
        today = date.today()
        end_date = today + timedelta(days=2)  # 3-day challenge: today + 2 days
        
        # Atomic challenge initialization
        user.challenge_active = True
        user.challenge_start_date = today
        user.challenge_end_date = end_date
        user.challenge_completed = False
        user.challenge_report_sent = False
        
        db.session.commit()
        
        # Emit challenge_started analytics event
        _emit_challenge_event("challenge_started", user_id_hash, {
            "challenge_type": "3-day",
            "start_date": today.isoformat(),
            "end_date": end_date.isoformat()
        })
        
        logger.info(f"Challenge started for user {user_id_hash[:8]}... - {today} to {end_date}")
        
        return {
            'text': "Welcome to the 3-Day Money Story challenge. Log once a day—simple.",
            'success': True,
            'challenge_started': True,
            'start_date': today.isoformat(),
            'end_date': end_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Challenge start error for user {user_id_hash[:8]}...: {e}")
        db.session.rollback()
        return {
            'text': "Unable to start challenge right now. Please try again.",
            'success': False,
            'error': str(e)
        }

def check_challenge_progress(user_id_hash: str, current_message: str) -> Optional[str]:
    """
    Check challenge progress and return daily nudge if appropriate
    Policy-compliant: only called during user interactions
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        current_message: Current user message (for context)
        
    Returns:
        Challenge nudge text if appropriate, None otherwise
    """
    try:
        user = db.session.query(User).filter_by(user_id_hash=user_id_hash).first()
        if not user or not user.challenge_active:
            return None
        
        today = date.today()
        
        # Check if challenge has expired and needs completion
        if today > user.challenge_end_date:
            return _handle_challenge_completion(user, user_id_hash)
        
        # Calculate current challenge day
        challenge_day = _calculate_current_challenge_day(user.challenge_start_date, today)
        
        # Only send nudges on Day 2 and Day 3
        if challenge_day in [2, 3]:
            # Check if we already sent a nudge today (daily cap)
            if user.last_milestone_date == today:
                return None  # Already nudged today
            
            # Send nudge and mark as sent today
            user.last_milestone_date = today
            db.session.commit()
            
            return f"Day {challenge_day}/3—keep logging!"
        
        return None
        
    except Exception as e:
        logger.error(f"Challenge progress check error for user {user_id_hash[:8]}...: {e}")
        return None

def _handle_challenge_completion(user: User, user_id_hash: str) -> Optional[str]:
    """
    Handle challenge completion logic with auto-report generation
    
    Args:
        user: User model instance
        user_id_hash: SHA-256 hashed user identifier
        
    Returns:
        Completion message with auto-report trigger
    """
    try:
        if user.challenge_report_sent:
            # Already processed completion
            user.challenge_active = False
            db.session.commit()
            return None
        
        # Check completion criteria - logged ≥1 entry on each of the 3 days
        completion_success = _check_challenge_completion_criteria(user_id_hash, user.challenge_start_date, user.challenge_end_date)
        
        # Mark challenge as completed
        user.challenge_active = False
        user.challenge_completed = completion_success
        user.challenge_report_sent = True
        
        db.session.commit()
        
        # Emit challenge_completed analytics event
        _emit_challenge_event("challenge_completed", user_id_hash, {
            "challenge_type": "3-day",
            "completed": completion_success,
            "start_date": user.challenge_start_date.isoformat(),
            "end_date": user.challenge_end_date.isoformat()
        })
        
        # Auto-generate REPORT with challenge completion source
        report_result = _generate_challenge_completion_report(user_id_hash, completion_success)
        
        # Emit report_requested analytics event
        _emit_challenge_event("report_requested", user_id_hash, {
            "source": "challenge_completion",
            "challenge_completed": completion_success
        })
        
        logger.info(f"Challenge completed for user {user_id_hash[:8]}... - success: {completion_success}")
        
        return report_result.get('text', 'Challenge completed!')
        
    except Exception as e:
        logger.error(f"Challenge completion error for user {user_id_hash[:8]}...: {e}")
        db.session.rollback()
        return None

def _check_challenge_completion_criteria(user_id_hash: str, start_date: date, end_date: date) -> bool:
    """
    Check if user logged ≥1 entry on each of the 3 challenge days
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        start_date: Challenge start date
        end_date: Challenge end date
        
    Returns:
        True if user logged on all 3 days
    """
    try:
        from models import Expense
        
        # Generate all 3 challenge days
        challenge_days = []
        current = start_date
        while current <= end_date:
            challenge_days.append(current)
            current += timedelta(days=1)
        
        # Check each day for logged expenses
        for challenge_day in challenge_days:
            expenses_on_day = db.session.query(Expense).filter(
                Expense.user_id_hash == user_id_hash,
                Expense.date == challenge_day
            ).count()
            
            if expenses_on_day == 0:
                return False  # Missed this day
        
        return True  # Logged on all 3 days
        
    except Exception as e:
        logger.error(f"Challenge completion criteria check error: {e}")
        return False

def _generate_challenge_completion_report(user_id_hash: str, completion_success: bool) -> Dict[str, Any]:
    """
    Auto-generate completion report for 3-Day Challenge
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        completion_success: Whether challenge was completed successfully
        
    Returns:
        Dict with report text and metadata
    """
    try:
        # Import existing report handlers to leverage infrastructure
        from handlers.summary import handle_summary
        
        if completion_success:
            # Generate success report with challenge context
            base_report = handle_summary(user_id_hash, "", "3days")  # 3-day timeframe
            
            if base_report.get('success', False):
                challenge_prefix = "🏆 3-Day Challenge Complete! Here's your Money Story:\n\n"
                report_text = challenge_prefix + base_report.get('text', '')
            else:
                report_text = "🏆 3-Day Challenge Complete! Great job logging every day. You're building strong financial awareness habits! 💪"
        else:
            # Generate gentle completion report
            base_report = handle_summary(user_id_hash, "", "3days")  # Still show what they did log
            
            if base_report.get('success', False):
                challenge_prefix = "Challenge ended. You missed a day—here's what you learned:\n\n"
                report_text = challenge_prefix + base_report.get('text', '')
            else:
                report_text = "Challenge ended. You missed a day—but every expense you logged is still valuable data for better spending awareness! 📊"
        
        # Increment reports_requested counter (following existing pattern)
        user = db.session.query(User).filter_by(user_id_hash=user_id_hash).first()
        if user:
            user.reports_requested += 1
            db.session.commit()
        
        return {
            'text': report_text,
            'success': True,
            'challenge_completion': completion_success,
            'source': 'challenge_completion'
        }
        
    except Exception as e:
        logger.error(f"Challenge completion report generation error: {e}")
        return {
            'text': "Challenge completed! Keep tracking your expenses for better financial insights.",
            'success': False,
            'error': str(e)
        }

def _calculate_current_challenge_day(start_date: date, current_date: date) -> int:
    """
    Calculate which day of the challenge it currently is
    
    Args:
        start_date: Challenge start date
        current_date: Current date
        
    Returns:
        Challenge day number (1, 2, or 3)
    """
    days_elapsed = (current_date - start_date).days
    return min(days_elapsed + 1, 3)  # Cap at day 3

def _calculate_days_remaining(start_date: date, end_date: date) -> int:
    """
    Calculate days remaining in challenge
    
    Args:
        start_date: Challenge start date
        end_date: Challenge end date
        
    Returns:
        Days remaining (0 if ended)
    """
    today = date.today()
    return max(0, (end_date - today).days)

def _emit_challenge_event(event_type: str, user_id_hash: str, event_data: Dict[str, Any]):
    """
    Emit challenge-related analytics events
    
    Args:
        event_type: Type of challenge event
        user_id_hash: SHA-256 hashed user identifier
        event_data: Event-specific data
    """
    try:
        # Use existing analytics infrastructure
        from utils.analytics_engine import analytics_engine
        
        # Follow existing event emission pattern
        analytics_engine._emit_analytics_event(event_type, user_id_hash, event_data)
        
        # Also log as structured event for comprehensive tracking
        log_structured_event(event_type.upper(), {
            "user_id": user_id_hash,
            **event_data
        }, user_id_hash)
        
    except Exception as e:
        logger.error(f"Challenge event emission error for {event_type}: {e}")

def get_challenge_status(user_id_hash: str) -> Dict[str, Any]:
    """
    Get current challenge status for a user
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        
    Returns:
        Dict with challenge status information
    """
    try:
        user = db.session.query(User).filter_by(user_id_hash=user_id_hash).first()
        if not user:
            return {'active': False, 'error': 'User not found'}
        
        if not user.challenge_active:
            return {'active': False}
        
        today = date.today()
        challenge_day = _calculate_current_challenge_day(user.challenge_start_date, today)
        days_remaining = _calculate_days_remaining(user.challenge_start_date, user.challenge_end_date)
        
        return {
            'active': True,
            'challenge_day': challenge_day,
            'days_remaining': days_remaining,
            'start_date': user.challenge_start_date.isoformat(),
            'end_date': user.challenge_end_date.isoformat(),
            'completed': user.challenge_completed
        }
        
    except Exception as e:
        logger.error(f"Challenge status check error: {e}")
        return {'active': False, 'error': str(e)}