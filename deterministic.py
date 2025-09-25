"""
Deterministic reply system - fast, reliable fallback
"""
from utils.categories import categorize_expense
from utils.parser import parse_expense


def deterministic_reply(message: str) -> str:
    """Generate deterministic response for any message"""
    message_lower = message.lower().strip()
    
    # Parse expense attempt
    parsed = parse_expense(message)
    
    if parsed["amount"] and parsed["description"]:
        # Expense logging
        category = categorize_expense(parsed["description"])
        return f"Logged ${parsed['amount']:.2f} for {parsed['description']} (category: {category})"
    
    elif "summary" in message_lower:
        return "Here's your expense summary: Total logged expenses available in dashboard."
    
    elif "help" in message_lower:
        return "I can help you log expenses. Try: 'log 25 coffee' or ask for 'summary'"
    
    elif "undo" in message_lower:
        return "Undo feature: Type 'undo last' to remove your most recent expense."
    
    else:
        # Generic helpful response
        return "I can help you track expenses. Try: 'log 25 coffee' or 'summary' for your spending overview."