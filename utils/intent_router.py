"""
Intent Router - Thin adapter to production router for backward compatibility
Provides intent detection functionality for message classification
"""

import re
from typing import Optional


def detect_intent(text: str) -> str:
    """
    Detect user intent from message text
    Returns intent type for routing decisions
    """
    if not text or not isinstance(text, str):
        return "UNKNOWN"
    
    # Normalize text for analysis
    text_lower = text.strip().lower()
    
    # Diagnostic commands
    if text_lower in ["diag", "diagnostic", "status", "health"]:
        return "DIAGNOSTIC"
    
    # Summary commands
    summary_patterns = [
        "summary", "total", "spent", "spending", "recap", "report", 
        "how much", "show me", "expenses", "overview"
    ]
    if any(pattern in text_lower for pattern in summary_patterns):
        return "SUMMARY"
    
    # Insight commands
    insight_patterns = [
        "insight", "advice", "tip", "analyze", "analysis", "pattern",
        "recommendations", "suggest", "improve", "save money"
    ]
    if any(pattern in text_lower for pattern in insight_patterns):
        return "INSIGHT"
    
    # Undo commands
    undo_patterns = ["undo", "delete", "remove", "cancel", "rollback", "mistake"]
    if any(pattern in text_lower for pattern in undo_patterns):
        return "UNDO"
    
    # Expense logging detection
    # Look for numbers and expense-related keywords
    has_number = bool(re.search(r'\d+', text))
    expense_keywords = [
        'spent', 'paid', 'bought', 'cost', 'price', 'coffee', 'lunch', 'dinner', 
        'food', 'gas', 'fuel', 'uber', 'taxi', 'restaurant', 'store', 'shop',
        'bill', 'meal', 'snack', 'drink', 'groceries', 'parking', 'transport'
    ]
    
    has_expense_keyword = any(keyword in text_lower for keyword in expense_keywords)
    
    # Simple heuristic: if it has a number and expense context, likely an expense
    if has_number and (has_expense_keyword or len(text.split()) <= 5):
        return "LOG_EXPENSE"
    
    # Default to unknown for non-matching text
    return "UNKNOWN"


# Preserve legacy import compatibility if needed
def route_intent(message, *, psid_hash, now, ai, db):
    """Legacy compatibility wrapper - routes to production router"""
    from utils.production_router import ProductionRouter
    router = ProductionRouter()
    return router.route_message(message, psid_hash, "")


def route_intent_v2(*args, **kwargs):
    """Alternative legacy compatibility wrapper"""
    return route_intent(*args, **kwargs)