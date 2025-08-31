"""
Message dispatcher: Routes messages to appropriate handlers based on intent
"""
import logging
from typing import Dict, Tuple, Optional
from utils.intent_router import detect_intent
from handlers.summary import handle_summary
from handlers.insight import handle_insight
from handlers.logger import handle_log
from handlers.report import handle_report

logger = logging.getLogger(__name__)

def handle_message_dispatch(user_id: str, text: str) -> Tuple[str, str]:
    """
    Dispatch message to appropriate handler based on intent
    Returns (response_text, intent) tuple
    """
    try:
        # Detect intent (priority order: commands before logging)
        intent = detect_intent(text)
        logger.info(f"Detected intent: {intent} for message: {text[:50]}")
        
        # Route to appropriate handler
        if intent == "REPORT":
            # Handle REPORT command - generate Money Story
            result = handle_report(user_id)
            primary_response = result.get('text', 'Report unavailable')
            
            # Check for challenge progress and append nudge if needed (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
                
            return primary_response, intent
            
        elif intent == "CHALLENGE_START":
            # Handle 3-Day Challenge start command (Block 6)
            from handlers.challenge import handle_challenge_start
            result = handle_challenge_start(user_id)
            return result.get('text', 'Challenge unavailable'), intent
            
        elif intent == "DIAGNOSTIC":
            # Handle diagnostic command
            diag_text = f"diag | type={type(user_id).__name__} | psid_hash={user_id[:8]}... | mode=STD"
            return diag_text, intent
            
        elif intent == "SUMMARY":
            result = handle_summary(user_id, text)  # Pass text for timeframe detection
            primary_response = result.get('text', 'Summary unavailable')
            
            # Check for challenge progress and append nudge if needed (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
                
            return primary_response, intent
            
        elif intent == "INSIGHT":
            result = handle_insight(user_id)
            primary_response = result.get('text', 'Insights unavailable')
            
            # Check for challenge progress and append nudge if needed (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
                
            return primary_response, intent
            
        elif intent == "LOG_EXPENSE":
            result = handle_log(user_id, text)
            primary_response = result.get('text', 'Unable to log expense')
            
            # Check for challenge progress after expense logging (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
                
            return primary_response, intent
            
        elif intent == "UNDO":
            # Simple undo handler
            primary_response = handle_undo(user_id)
            
            # Check for challenge progress and append nudge if needed (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
                
            return primary_response, intent
            
        elif intent == "CLARIFY_SPENDING_INTENT":
            # Handle spending contradiction clarification with coach-tone
            primary_response = "🤔 I want to make sure I help you the right way! Are you looking for tips to spend *less* and save more money, or do you actually want to increase your spending? Just want to point my advice in the right direction! 💡"
            
            # Check for challenge progress and append nudge if needed (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
                
            return primary_response, intent
            
        elif intent == "UNKNOWN":
            # Ask for clarification when we don't understand something
            import random
            clarification_responses = [
                "I'm not sure what you mean by that. Could you clarify? I'm here to help with your spending and finances! 💰",
                "That's not something I recognize - could you explain what you're looking for? I can help with expenses, budgets, and financial insights! 📊",
                "I don't quite understand that term. Mind clarifying? I'm great with tracking spending and giving money advice! 💡",
                "Not sure I follow - could you rephrase that? I specialize in expense tracking and financial guidance! 🎯"
            ]
            primary_response = random.choice(clarification_responses)
            
            # Check for challenge progress and append nudge if needed (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
                
            return primary_response, "CLARIFICATION"
            
        else:
            # Engaging help responses with variety
            import random
            help_responses = [
                "I'm here to help with your finances! What would you like to know?",
                "Not quite sure what you're looking for, but I'm great with money stuff! Try asking about your spending or logging an expense",
                "I can help with your financial tracking! Want to see your spending summary or add a new expense?",
                "Ready to assist with your money! How about checking your spending patterns or logging a purchase?",
                "I'm your financial companion! Try asking for insights, summaries, or expense logging"
            ]
            primary_response = random.choice(help_responses)
            
            # Check for challenge progress and append nudge if needed (Block 6)
            challenge_nudge = _check_and_append_challenge_progress(user_id, text)
            if challenge_nudge:
                primary_response += f"\n\n{challenge_nudge}"
            
            return primary_response, "HELP"
            
    except Exception as e:
        logger.error(f"Dispatcher error: {e}")
        return "Something went wrong. Please try again.", "ERROR"

def handle_undo(user_id: str) -> str:
    """Simple undo handler - removes last expense"""
    try:
        from models import Expense
        from app import db
        
        # Get last expense
        last_expense = db.session.query(Expense).filter_by(
            user_id=user_id
        ).order_by(Expense.created_at.desc()).first()
        
        if last_expense:
            amount = last_expense.amount
            category = last_expense.category
            db.session.delete(last_expense)
            db.session.commit()
            return f"✅ Removed last expense: {amount:.0f} BDT from {category}"
        else:
            return "No expenses to undo."
            
    except Exception as e:
        logger.error(f"Undo error: {e}")
        return "Unable to undo. Please try again."

def _check_and_append_challenge_progress(user_id_hash: str, current_message: str) -> Optional[str]:
    """
    Check challenge progress during user interaction and return nudge if appropriate
    Policy-compliant: only called during user interactions, never scheduled
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        current_message: Current user message
        
    Returns:
        Challenge nudge text if appropriate, None otherwise
    """
    try:
        from handlers.challenge import check_challenge_progress
        return check_challenge_progress(user_id_hash, current_message)
    except Exception as e:
        logger.error(f"Challenge progress check error: {e}")
        return None