"""
Smart Reminder System - 23-Hour Compliant
Handles reminder scheduling, checking, and sending within Facebook's 24-hour policy
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from app import db
from models import User
from utils.facebook_handler import send_facebook_message

logger = logging.getLogger(__name__)

def check_and_send_reminders() -> Dict[str, int]:
    """
    Check for users with scheduled reminders and send them if within the safe window.
    
    Returns:
        Dict with reminder statistics
    """
    stats = {
        'checked': 0,
        'sent': 0,
        'skipped_window': 0,
        'skipped_too_early': 0,
        'errors': 0
    }
    
    try:
        now = datetime.utcnow()
        
        # Find users with scheduled reminders that are due
        users_with_reminders = db.session.query(User).filter(
            User.reminder_scheduled_for.isnot(None),
            User.reminder_scheduled_for <= now,
            User.reminder_preference != 'none'
        ).all()
        
        stats['checked'] = len(users_with_reminders)
        
        for user in users_with_reminders:
            try:
                if _should_send_reminder(user, now):
                    success = _send_reminder_message(user, now)
                    if success:
                        stats['sent'] += 1
                        # Clear the scheduled reminder
                        user.reminder_scheduled_for = None
                        user.last_reminder_sent = now
                    else:
                        stats['errors'] += 1
                else:
                    stats['skipped_window'] += 1
                    # Clear expired reminder to avoid repeated checking
                    user.reminder_scheduled_for = None
                    
            except Exception as e:
                logger.error(f"Error processing reminder for user {user.user_id_hash[:8]}...: {e}")
                stats['errors'] += 1
        
        # Commit all updates
        db.session.commit()
        
        if stats['sent'] > 0 or stats['errors'] > 0:
            logger.info(f"Reminder check complete: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Error in reminder check: {e}")
        db.session.rollback()
        stats['errors'] += 1
        return stats

def _should_send_reminder(user: User, now: datetime) -> bool:
    """
    Check if we should send a reminder to this user based on 24-hour policy.
    
    Args:
        user: User object
        now: Current timestamp
        
    Returns:
        True if safe to send reminder
    """
    # Check if within 24-hour window
    if not user.last_user_message_at:
        logger.warning(f"User {user.user_id_hash[:8]}... has no last_user_message_at timestamp")
        return False
    
    hours_since_last_message = (now - user.last_user_message_at).total_seconds() / 3600
    
    # Must be within 23.5 hours for safety margin
    if hours_since_last_message >= 23.5:
        logger.info(f"Skipping reminder for {user.user_id_hash[:8]}... - {hours_since_last_message:.1f}h since last message")
        return False
    
    # Don't send if we already sent one recently (avoid spam)
    if user.last_reminder_sent:
        hours_since_last_reminder = (now - user.last_reminder_sent).total_seconds() / 3600
        if hours_since_last_reminder < 20:  # At least 20 hours between reminders
            return False
    
    return True

def _send_reminder_message(user: User, now: datetime) -> bool:
    """
    Send a reminder message to the user.
    
    Args:
        user: User object
        now: Current timestamp
        
    Returns:
        True if message sent successfully
    """
    try:
        # Get user's PSID from user_id_hash (we need to reverse the hash lookup)
        # Since we can't reverse SHA-256, we'll need to modify this approach
        # For now, we'll log this limitation
        logger.warning("Cannot send reminder - PSID lookup not implemented yet")
        return False
        
        # TODO: Implement PSID lookup or store PSIDs directly
        # reminder_text = _generate_reminder_text(user)
        # return send_facebook_message(psid, reminder_text)
        
    except Exception as e:
        logger.error(f"Error sending reminder: {e}")
        return False

def _generate_reminder_text(user: User) -> str:
    """
    Generate personalized reminder text.
    
    Args:
        user: User object
        
    Returns:
        Reminder message text
    """
    if user.first_name:
        greeting = f"Hi {user.first_name}!"
    else:
        greeting = "Hi there!"
    
    messages = [
        f"🌙 {greeting} How did your spending go today?",
        f"💰 {greeting} Ready to log today's expenses?",
        f"📝 {greeting} Any purchases to track before bed?"
    ]
    
    # Rotate based on user ID to avoid repetition
    index = len(user.user_id_hash) % len(messages)
    return messages[index]

def schedule_reminder(user_id_hash: str, hours_from_now: float = 23.0) -> bool:
    """
    Schedule a reminder for a user.
    
    Args:
        user_id_hash: User's hash
        hours_from_now: Hours from now to schedule reminder
        
    Returns:
        True if reminder scheduled successfully
    """
    try:
        user = db.session.query(User).filter_by(user_id_hash=user_id_hash).first()
        if not user:
            return False
        
        # Schedule reminder for specified time
        reminder_time = datetime.utcnow() + timedelta(hours=hours_from_now)
        user.reminder_scheduled_for = reminder_time
        user.reminder_preference = 'daily'
        
        db.session.commit()
        
        logger.info(f"Reminder scheduled for {user_id_hash[:8]}... at {reminder_time}")
        return True
        
    except Exception as e:
        logger.error(f"Error scheduling reminder: {e}")
        db.session.rollback()
        return False

def cancel_reminders(user_id_hash: str) -> bool:
    """
    Cancel all reminders for a user.
    
    Args:
        user_id_hash: User's hash
        
    Returns:
        True if canceled successfully
    """
    try:
        user = db.session.query(User).filter_by(user_id_hash=user_id_hash).first()
        if not user:
            return False
        
        user.reminder_scheduled_for = None
        user.reminder_preference = 'none'
        
        db.session.commit()
        
        logger.info(f"Reminders canceled for {user_id_hash[:8]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error canceling reminders: {e}")
        db.session.rollback()
        return False