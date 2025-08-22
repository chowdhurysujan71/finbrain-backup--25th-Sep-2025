"""
Coach-tone Reply Templates for FinBrain
Provides consistent, friendly messaging across STD and AI modes
"""

import random
from typing import Optional, Dict, Any
from decimal import Decimal

# Currency symbol mapping
CURRENCY_SYMBOLS = {
    'BDT': '৳',
    'USD': '$',
    'GBP': '£', 
    'EUR': '€',
    'INR': '₹'
}

def get_currency_symbol(currency: str) -> str:
    """Get currency symbol for display"""
    return CURRENCY_SYMBOLS.get(currency.upper(), currency)

def format_expense_logged_reply(amount: Decimal, currency: str, category: str, 
                               merchant: Optional[str] = None, 
                               weekly_total: Optional[Decimal] = None,
                               category_share: Optional[str] = None) -> str:
    """
    Format coach-tone reply for successful expense logging.
    
    Template: Acknowledge + Insight + Next Action
    
    Args:
        amount: Expense amount
        currency: Currency code (BDT, USD, etc)
        category: Expense category 
        merchant: Optional merchant name
        weekly_total: Optional 7-day total for insight
        category_share: Optional category percentage for insight
        
    Returns:
        Formatted reply string
    """
    currency_symbol = get_currency_symbol(currency)
    merchant_part = f" at {merchant}" if merchant else ""
    
    # Acknowledge
    acknowledge = f"Logged {currency_symbol}{amount:.0f} for {category}{merchant_part}."
    
    # Insight (if data available)
    insights = []
    if weekly_total and weekly_total > 0:
        insights.append(f"This week: {currency_symbol}{weekly_total:.0f}")
    
    if category_share:
        insights.append(f"{category} is {category_share} of spending")
    
    insight_part = " " + " • ".join(insights) if insights else ""
    
    # Next action
    next_actions = [
        "Type 'summary' to see your week or 'insight' for a tip.",
        "Say 'summary' for your overview or 'insight' for advice.",
        "Try 'summary' for weekly view or 'insight' for optimization tips."
    ]
    next_action = random.choice(next_actions)
    
    return f"{acknowledge}{insight_part} {next_action}"

def format_duplicate_reply(timestamp: str, amount: Optional[Decimal] = None, 
                          currency: Optional[str] = None) -> str:
    """
    Format reply for duplicate expense detection.
    
    Args:
        timestamp: When original expense was logged
        amount: Optional amount for context
        currency: Optional currency for context
        
    Returns:
        Formatted duplicate detection reply
    """
    amount_part = ""
    if amount and currency:
        currency_symbol = get_currency_symbol(currency)
        amount_part = f" ({currency_symbol}{amount:.0f})"
    
    return f"Looks like a repeat—already logged at {timestamp}{amount_part}. Reply 'yes' to log again or 'summary' to see your expenses."

def format_help_reply(is_new_user: bool = False) -> str:
    """
    Format helpful reply for non-expense messages.
    
    Args:
        is_new_user: Whether user is new (affects messaging)
        
    Returns:
        Formatted help reply
    """
    if is_new_user:
        return ("Welcome to FinBrain! I help track your expenses. "
                "Try: • 'spent 100 on lunch' - to log an expense "
                "• 'summary' - to see your spending "
                "• 'insight' - for optimization tips")
    else:
        return ("I can help you track expenses! "
                "Try: • 'spent 100 on lunch' - to log an expense "
                "• 'summary' - to see your spending "
                "• 'insight' - for optimization tips")

def format_error_reply(error_context: str = "general") -> str:
    """
    Format user-friendly error reply.
    
    Args:
        error_context: Context of error (parsing, saving, etc)
        
    Returns:
        Formatted error reply
    """
    error_messages = {
        "parsing": "I couldn't understand that expense. Try: 'spent 100 on lunch' or '৳50 coffee'",
        "saving": "Unable to save that expense right now. Please try again in a moment.",
        "general": "Something went wrong. Please try again or type 'help' for examples."
    }
    
    return error_messages.get(error_context, error_messages["general"])

def format_summary_intro(user_name: Optional[str] = None, 
                        period: str = "week") -> str:
    """
    Format intro for summary responses.
    
    Args:
        user_name: Optional user first name
        period: Time period (week, month, etc)
        
    Returns:
        Formatted summary intro
    """
    name_part = f"{user_name}, " if user_name else ""
    return f"Here's {name_part}your {period} so far:"

def format_no_expenses_reply(period: str = "week") -> str:
    """
    Format reply when user has no expenses in period.
    
    Args:
        period: Time period being queried
        
    Returns:
        Formatted no expenses reply
    """
    encouragement = [
        f"No expenses logged this {period} yet! Start with 'spent 100 on lunch'",
        f"Clean slate for this {period}! Log your first expense: 'coffee 50'", 
        f"Fresh start this {period}! Try logging: '৳100 for groceries'"
    ]
    
    return random.choice(encouragement)

# Template constants for consistency
COACH_TONE_PRINCIPLES = {
    "acknowledge_first": "Always acknowledge the user's action",
    "provide_context": "Add relevant spending insights when available", 
    "guide_next_step": "Suggest logical next actions",
    "stay_concise": "Keep under 280 characters when possible",
    "be_encouraging": "Use positive, supportive language"
}

def validate_reply_length(reply: str, max_chars: int = 280) -> str:
    """
    Ensure reply stays within character limits.
    
    Args:
        reply: The formatted reply
        max_chars: Maximum character limit
        
    Returns:
        Truncated reply if needed
    """
    if len(reply) <= max_chars:
        return reply
    
    # Graceful truncation
    truncated = reply[:max_chars-3] + "..."
    return truncated