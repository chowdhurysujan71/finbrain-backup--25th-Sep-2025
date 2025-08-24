"""
Message dispatcher: Routes messages to appropriate handlers based on intent
"""
import logging
from typing import Dict, Tuple
from utils.intent_router import detect_intent
from handlers.summary import handle_summary
from handlers.insight import handle_insight
from handlers.logger import handle_log

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
        if intent == "DIAGNOSTIC":
            # Handle diagnostic command
            diag_text = f"diag | type={type(user_id).__name__} | psid_hash={user_id[:8]}... | mode=STD"
            return diag_text, intent
            
        elif intent == "SUMMARY":
            result = handle_summary(user_id)
            return result.get('text', 'Summary unavailable'), intent
            
        elif intent == "INSIGHT":
            result = handle_insight(user_id)
            return result.get('text', 'Insights unavailable'), intent
            
        elif intent == "LOG_EXPENSE":
            result = handle_log(user_id, text)
            return result.get('text', 'Unable to log expense'), intent
            
        elif intent == "UNDO":
            # Simple undo handler
            return handle_undo(user_id), intent
            
        elif intent == "CLARIFY_SPENDING_INTENT":
            # Handle spending contradiction clarification with coach-tone
            return "🤔 I want to make sure I help you the right way! Are you looking for tips to spend *less* and save more money, or do you actually want to increase your spending? Just want to point my advice in the right direction! 💡", intent
            
        else:
            # Unknown intent - provide help
            return (
                "I can help you track expenses! Try:\n"
                "• 'spent 100 on lunch' - to log an expense\n"
                "• 'summary' - to see your spending\n"
                "• 'insight' - for optimization tips"
            ), "HELP"
            
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