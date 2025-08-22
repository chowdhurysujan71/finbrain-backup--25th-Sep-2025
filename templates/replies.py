"""
FinBrain Template Replies: Coach-style messaging for corrections and general responses
Provides consistent, encouraging tone across STD and AI modes
"""

from typing import Optional
from decimal import Decimal

def format_corrected_reply(old_amount: float, old_currency: str, new_amount: float, 
                         new_currency: str, category: str, merchant: Optional[str] = None) -> str:
    """
    Format coach-style confirmation for successful correction.
    
    Args:
        old_amount: Original expense amount
        old_currency: Original currency  
        new_amount: Corrected amount
        new_currency: Corrected currency
        category: Expense category
        merchant: Optional merchant name
        
    Returns:
        Formatted confirmation message
    """
    # Format currency symbols
    old_symbol = '৳' if old_currency == 'BDT' else old_currency
    new_symbol = '৳' if new_currency == 'BDT' else new_currency
    
    # Build merchant part
    merchant_part = ""
    if merchant:
        merchant_part = f" at {merchant}"
    
    # Create confirmation message
    category_display = category if category != 'general' else 'expense'
    
    base_msg = f"Got it — corrected {category_display} from {old_symbol}{old_amount:.0f} → {new_symbol}{new_amount:.0f}{merchant_part}."
    
    # Add next step suggestion (keep under 280 chars total)
    if len(base_msg) < 220:
        base_msg += " Type 'summary' to review your week."
    
    return base_msg

def format_correction_no_candidate_reply(amount: Decimal, currency: str, category: str) -> str:
    """
    Format reply when no expense found to correct - logged as new.
    
    Args:
        amount: New expense amount
        currency: Currency
        category: Expense category
        
    Returns:
        Formatted message explaining it was logged as new
    """
    symbol = '৳' if currency == 'BDT' else currency
    category_display = category if category != 'general' else 'expense'
    
    return f"Logged {category_display} {symbol}{amount:.0f} as new. No recent expense found to correct. Type 'summary' to see totals."

def format_correction_duplicate_reply() -> str:
    """
    Format reply for duplicate correction attempts.
    
    Returns:
        Polite message about duplicate request
    """
    return "I've already processed that correction request. Type 'summary' to see your updated totals."

def format_correction_confirmation_request(old_amount: float, old_currency: str, category: str) -> str:
    """
    Format confirmation request for corrections outside the time window.
    
    Args:
        old_amount: Amount of expense to correct
        old_currency: Currency of old expense  
        category: Category of old expense
        
    Returns:
        Confirmation request message
    """
    symbol = '৳' if old_currency == 'BDT' else old_currency
    category_display = category if category != 'general' else 'expense'
    
    return f"Replace your last {category_display} ({symbol}{old_amount:.0f}) from earlier? Reply 'yes' to confirm or ignore to log as new."

def format_expense_logged_reply(amount: Decimal, currency: str, category: str, 
                               merchant: Optional[str] = None) -> str:
    """
    Format coach-style confirmation for regular expense logging.
    
    Args:
        amount: Expense amount
        currency: Currency
        category: Expense category  
        merchant: Optional merchant name
        
    Returns:
        Formatted confirmation message
    """
    symbol = '৳' if currency == 'BDT' else currency
    merchant_part = f" at {merchant}" if merchant else ""
    category_display = category if category != 'general' else 'expense'
    
    base_msg = f"Logged {category_display} {symbol}{amount:.0f}{merchant_part}."
    
    # Add encouragement if space allows
    if len(base_msg) < 200:
        base_msg += " Great job tracking your spending!"
    
    return base_msg

def format_duplicate_reply() -> str:
    """
    Format reply for duplicate expense logging attempts.
    
    Returns:
        Friendly duplicate message
    """
    return "Already logged that expense! Type 'summary' to see your totals."

def format_help_reply() -> str:
    """
    Format standard help message.
    
    Returns:
        Help message with examples
    """
    return ("I help track expenses! Try:\n"
            "• 'spent 100 on lunch' - log expense\n" 
            "• 'summary' - see totals\n"
            "• 'actually 500' - fix last amount")

def format_parsing_error_reply() -> str:
    """
    Format reply when expense parsing fails.
    
    Returns:
        Helpful error message
    """
    return "I didn't catch the amount. Try like: 'spent 100 on coffee' or '৳500 lunch'."

# Legacy compatibility functions

def format_logged_response(amount: float, description: str, category: str) -> str:
    """Legacy compatibility wrapper for expense logging."""
    return format_expense_logged_reply(Decimal(str(amount)), 'BDT', category)

def format_summary_response(totals: dict, tip: str) -> str:
    """Format summary response with tip."""
    total = totals.get('total', 0)
    return f"Week: ৳{total:.0f} total. {tip}"

def format_help_response() -> str:
    """Legacy compatibility wrapper for help."""
    return format_help_reply()

def format_undo_response(amount: Optional[float] = None, note: Optional[str] = None) -> str:
    """Format undo confirmation."""
    if amount:
        return f"Removed ৳{amount:.0f} expense. Type 'summary' for updated totals."
    else:
        return "Nothing recent to undo. All your expenses are still tracked!"