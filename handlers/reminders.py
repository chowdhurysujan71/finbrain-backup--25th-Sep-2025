"""
Smart Reminder Handler
Handles reminder consent, user-initiated reminder requests, and cancellations
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime

from db_base import db
from models import User
from utils.smart_reminders import schedule_reminder, cancel_reminders

logger = logging.getLogger("handlers.reminders")

def handle_reminder_consent(psid_hash_val: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Handle user consent to reminder prompts.
    
    Args:
        psid_hash_val: User's PSID hash
        text: User's response text
        
    Returns:
        Response dict if consent detected, None otherwise
    """
    text_lower = text.lower().strip()
    
    # Positive consent patterns
    consent_patterns = [
        r'^(?:yes|yeah|yep|sure|ok|okay|y)$',
        r'^(?:yes|yeah|yep|sure)\s*(?:please|plz)?\.?$',
        r'^(?:that would be|that\'s) (?:great|good|helpful|nice)\.?$',
        r'^(?:i would like that|i\'d like that)\.?$'
    ]
    
    for pattern in consent_patterns:
        if re.match(pattern, text_lower):
            # User consented to reminders
            success = schedule_reminder(psid_hash_val, hours_from_now=23.0)
            
            if success:
                logger.info(f"Reminder consent granted for {psid_hash_val[:8]}...")
                return {
                    'text': "📅 Perfect! I'll check in with you tomorrow evening. You can say 'stop reminders' anytime.",
                    'intent': 'reminder_consent_granted',
                    'category': None,
                    'amount': None
                }
            else:
                return {
                    'text': "I'll try to remind you tomorrow evening!",
                    'intent': 'reminder_consent_error',
                    'category': None,
                    'amount': None
                }
    
    # Negative consent patterns
    decline_patterns = [
        r'^(?:no|nope|nah|not now)\.?$',
        r'^(?:no|nope)\s*(?:thanks|thank you|thx)\.?$',
        r'^(?:not interested|no need)\.?$'
    ]
    
    for pattern in decline_patterns:
        if re.match(pattern, text_lower):
            logger.info(f"Reminder consent declined for {psid_hash_val[:8]}...")
            return {
                'text': "No problem! You can always ask me to 'remind me daily' later if you change your mind.",
                'intent': 'reminder_consent_declined',
                'category': None,
                'amount': None
            }
    
    return None

def handle_reminder_request(psid_hash_val: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Handle user-initiated reminder requests.
    
    Args:
        psid_hash_val: User's PSID hash
        text: User's message text
        
    Returns:
        Response dict if reminder request detected, None otherwise
    """
    text_lower = text.lower().strip()
    
    # User-initiated reminder patterns
    request_patterns = [
        r'remind me (?:daily|every day|each day)',
        r'(?:set|schedule) (?:a )?(?:daily )?reminder',
        r'i want (?:daily )?reminders?',
        r'can you remind me (?:daily|every day)',
        r'send me (?:daily )?reminders?'
    ]
    
    for pattern in request_patterns:
        if re.search(pattern, text_lower):
            # User requested reminders
            success = schedule_reminder(psid_hash_val, hours_from_now=23.0)
            
            if success:
                logger.info(f"Daily reminder requested by {psid_hash_val[:8]}...")
                return {
                    'text': "✅ Daily reminders enabled! I'll check in with you each evening as long as you message me regularly.",
                    'intent': 'reminder_requested',
                    'category': None,
                    'amount': None
                }
            else:
                return {
                    'text': "I'll set up daily reminders for you!",
                    'intent': 'reminder_request_error',
                    'category': None,
                    'amount': None
                }
    
    return None

def handle_reminder_cancellation(psid_hash_val: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Handle reminder cancellation requests.
    
    Args:
        psid_hash_val: User's PSID hash
        text: User's message text
        
    Returns:
        Response dict if cancellation detected, None otherwise
    """
    text_lower = text.lower().strip()
    
    # Cancellation patterns
    cancel_patterns = [
        r'stop reminders?',
        r'cancel reminders?',
        r'turn off reminders?',
        r'disable reminders?',
        r'no more reminders?',
        r'don\'t remind me',
        r'unsubscribe'
    ]
    
    for pattern in cancel_patterns:
        if re.search(pattern, text_lower):
            # User wants to cancel reminders
            success = cancel_reminders(psid_hash_val)
            
            if success:
                logger.info(f"Reminders canceled for {psid_hash_val[:8]}...")
                return {
                    'text': "✅ Got it, I'll stop daily reminders. You can re-enable anytime with 'remind me daily'.",
                    'intent': 'reminder_canceled',
                    'category': None,
                    'amount': None
                }
            else:
                return {
                    'text': "Reminders stopped!",
                    'intent': 'reminder_cancel_error',
                    'category': None,
                    'amount': None
                }
    
    return None

def detect_reminder_intent(psid_hash_val: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Main function to detect and handle all reminder-related intents.
    
    Args:
        psid_hash_val: User's PSID hash
        text: User's message text
        
    Returns:
        Response dict if any reminder intent detected, None otherwise
    """
    # CRITICAL FIX: Check for active feedback context FIRST
    # If user has pending feedback on a Money Story report, don't intercept YES/NO responses
    try:
        from utils.feedback_context import FeedbackContextManager
        context_manager = FeedbackContextManager()
        
        # If there's active feedback context, let feedback handler process YES/NO responses
        if context_manager.has_active_context(psid_hash_val):
            logger.debug(f"Skipping reminder detection for {psid_hash_val[:8]}... - active feedback context detected")
            return None
    except Exception as e:
        # Fail-open: if feedback context check fails, continue with reminder processing
        logger.warning(f"Feedback context check failed in reminder detection: {e}")
    
    # Check for consent (highest priority - user responding to our prompt)
    consent_response = handle_reminder_consent(psid_hash_val, text)
    if consent_response:
        return consent_response
    
    # Check for cancellation
    cancel_response = handle_reminder_cancellation(psid_hash_val, text)
    if cancel_response:
        return cancel_response
    
    # Check for new reminder request
    request_response = handle_reminder_request(psid_hash_val, text)
    if request_response:
        return request_response
    
    return None