"""
Message dispatcher: Routes messages to appropriate handlers based on intent
"""
import logging
from typing import Dict, Tuple
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
            return result.get('text', 'Report unavailable'), intent
            
        elif intent == "DIAGNOSTIC":
            # Handle diagnostic command
            diag_text = f"diag | type={type(user_id).__name__} | psid_hash={user_id[:8]}... | mode=STD"
            return diag_text, intent
            
        elif intent == "SUMMARY":
            result = handle_summary(user_id, text)  # Pass text for timeframe detection
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
            
        elif intent == "UNKNOWN":
            # Ask for clarification when we don't understand something
            import random
            clarification_responses = [
                "I'm not sure what you mean by that. Could you clarify? I'm here to help with your spending and finances! 💰",
                "That's not something I recognize - could you explain what you're looking for? I can help with expenses, budgets, and financial insights! 📊",
                "I don't quite understand that term. Mind clarifying? I'm great with tracking spending and giving money advice! 💡",
                "Not sure I follow - could you rephrase that? I specialize in expense tracking and financial guidance! 🎯"
            ]
            return random.choice(clarification_responses), "CLARIFICATION"
            
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
            return random.choice(help_responses), "HELP"
            
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