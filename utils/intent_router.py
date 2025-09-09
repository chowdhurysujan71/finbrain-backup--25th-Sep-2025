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
    
    # Contradiction guard for INSIGHT - check for spending increase requests
    if _has_spending_increase_intent(text_lower):
        return "CLARIFY_SPENDING_INTENT"
    
    # REPORT command - exact match (case-insensitive)  
    if text_lower == "report":
        return "REPORT"
    
    # 3-Day Challenge start command (Block 6)
    challenge_patterns = ["start 3d", "start3d", "3d challenge", "start challenge", "start 3d challenge"]
    if text_lower in challenge_patterns or any(pattern in text_lower for pattern in ["start 3d", "3d challenge"]):
        return "CHALLENGE_START"
    
    # Diagnostic commands
    if text_lower in ["diag", "diagnostic", "status", "health"]:
        return "DIAGNOSTIC"
    
    # Enhanced SUMMARY detection using production router patterns
    from utils.production_router import _is_summary_command
    if _is_summary_command(text):
        return "SUMMARY"
        
    # EXPENSE LOGGING DETECTION - MOVED UP FOR PRIORITY
    # Hot guardrail: if message contains money, prioritize expense logging
    from finbrain.router import contains_money
    if contains_money(text):
        # Double-check with keyword patterns for expense context
        has_number = bool(re.search(r'\d+', text))
        expense_keywords = [
            'spent', 'paid', 'bought', 'cost', 'price', 'coffee', 'lunch', 'dinner', 
            'food', 'gas', 'fuel', 'uber', 'taxi', 'restaurant', 'store', 'shop',
            'bill', 'meal', 'snack', 'drink', 'groceries', 'parking', 'transport',
            'taka', 'tk', 'rupees', 'dollars', 'euro', 'pound'
        ]
        has_expense_keyword = any(keyword in text_lower for keyword in expense_keywords)
        
        if has_number and has_expense_keyword:
            return "LOG_EXPENSE"
        
    # Enhanced INSIGHT detection using production router patterns  
    from utils.production_router import _is_insight_command
    if _is_insight_command(text):
        return "INSIGHT"
    
    # Category-specific queries - New intent type for specific category breakdowns
    category_keywords = [
        "food", "transport", "transportation", "groceries", "grocery", "dining", "restaurant",
        "coffee", "entertainment", "shopping", "gas", "fuel", "uber", "taxi", "bills",
        "utilities", "rent", "housing", "health", "medical", "pharmacy", "clothes", "clothing"
    ]
    
    # Check for category-specific spending queries
    category_query_patterns = [
        "how much did i spend on", "what did i spend on", "how much on",
        "spent on", "spending on", "expenses on", "cost of", "total for"
    ]
    
    if any(pattern in text_lower for pattern in category_query_patterns):
        for category in category_keywords:
            if category in text_lower:
                return "CATEGORY_BREAKDOWN"
    
    # Check for "food this month", "transport this week" pattern
    if any(category in text_lower for category in category_keywords):
        if any(timeframe in text_lower for timeframe in ["this month", "this week", "last week", "last month", "today", "yesterday"]):
            return "CATEGORY_BREAKDOWN"

    # SECONDARY EXPENSE CHECK - Fallback for edge cases not caught above
    # Look for numbers and expense-related keywords first
    has_number = bool(re.search(r'\d+', text))
    expense_keywords = [
        'spent', 'paid', 'bought', 'cost', 'price', 'coffee', 'lunch', 'dinner', 
        'food', 'gas', 'fuel', 'uber', 'taxi', 'restaurant', 'store', 'shop',
        'bill', 'meal', 'snack', 'drink', 'groceries', 'parking', 'transport',
        'taka', 'tk', 'rupees', 'dollars', 'euro', 'pound'
    ]
    
    has_expense_keyword = any(keyword in text_lower for keyword in expense_keywords)
    
    # Strong expense indicators with amounts - prioritize over summary
    if has_number and has_expense_keyword:
        return "LOG_EXPENSE"
    
    # Summary commands - Enhanced to catch natural questions
    summary_patterns = [
        "summary", "total", "recap", "report", 
        "show me", "expenses", "overview", "costs",
        # Natural questions that should be summaries (excluding specific category queries)
        "what did i spend", "what have i spent", "how much did i spend",
        "my expenses", "expenses this", "expenses last", "expenses for",
        "yesterday", "today", "this week", "last week", "this month"
    ]
    # Remove generic "spent" and "spend" to avoid conflicts with expense logging
    if any(pattern in text_lower for pattern in summary_patterns):
        return "SUMMARY"
    
    # Privacy/security queries - Enhanced synonyms for data security questions
    privacy_patterns = [
        "store my data", "how do you store my data", "how do you store data",
        "is my data safe", "data secure", "data security", "data protection",
        "privacy", "privacy policy", "how is my data stored"
    ]
    if any(pattern in text_lower for pattern in privacy_patterns):
        return "INFO_PRIVACY"

    # Insight commands - Enhanced keyword set for ASK_INSIGHT detection
    insight_patterns = [
        "insight", "insights", "advice", "advise", "tip", "tips", "analyze", "analysis", 
        "pattern", "recommendations", "suggest", "suggestion", "suggestions", "improve", 
        "save money", "optimize", "optimization", "breakdown", "review", 
        "how am i doing", "help me save", "reduce spend", "increase savings"
    ]
    if any(pattern in text_lower for pattern in insight_patterns):
        return "INSIGHT"
    
    # Correction/clarification patterns - detect when user is correcting previous expense
    correction_patterns = [
        "wait", "actually", "correction", "i meant", "make that", "change to", "it was",
        "sorry", "no wait", "hold on", "let me correct", "i said", "i bought", "i got",
        "it should be", "change that", "update that", "fix that", "that was wrong"
    ]
    
    quantity_correction_patterns = [
        "it was two", "it was three", "it was four", "it was five", "make it two", "make it three",
        "actually two", "actually three", "two of", "three of", "multiple", "several"
    ]
    
    # Check for correction intent
    if any(pattern in text_lower for pattern in correction_patterns):
        return "LOG_EXPENSE"  # Treat corrections as new expense entries for now
    
    if any(pattern in text_lower for pattern in quantity_correction_patterns):
        return "LOG_EXPENSE"
    
    # Natural clarification like "I bought two beef steak omelettes"
    if text_lower.startswith("i bought") or text_lower.startswith("i got") or text_lower.startswith("i had"):
        return "LOG_EXPENSE"

    # Undo commands
    undo_patterns = ["undo", "delete", "remove", "cancel", "rollback", "mistake"]
    if any(pattern in text_lower for pattern in undo_patterns):
        return "UNDO"
    
    # Fallback expense detection for short messages with numbers
    has_number = bool(re.search(r'\d+', text))
    if has_number and len(text.split()) <= 5:
        return "LOG_EXPENSE"
    
    # Default to unknown for non-matching text
    return "UNKNOWN"


def _has_spending_increase_intent(text_lower: str) -> bool:
    """
    Check if text contains contradictory spending increase intent
    Returns True if user wants to increase spending (contradiction to typical insights)
    """
    increase_patterns = [
        "increase my spending", "spend more", "spending more", "increase spending",
        "spend more money", "want to spend more", "increase my expenses",
        "higher spending", "spend higher", "more money"
    ]
    return any(pattern in text_lower for pattern in increase_patterns)


def is_followup_after_summary_or_log(text: str, previous_intent: Optional[str] = None) -> bool:
    """
    Check if current text is INSIGHT request following SUMMARY or LOG response
    Args:
        text: Current user message
        previous_intent: Previous bot response intent (SUMMARY, LOG, etc.)
    Returns:
        True if this should be upgraded from normal intent to INSIGHT
    """
    if not previous_intent or previous_intent not in ["SUMMARY", "LOG"]:
        return False
        
    # Check if current text contains insight keywords
    text_lower = text.strip().lower()
    insight_patterns = [
        "insight", "insights", "advice", "advise", "tip", "tips", "analyze", "analysis",
        "pattern", "recommendations", "suggest", "suggestion", "suggestions", "improve",
        "save money", "optimize", "optimization", "breakdown", "review",
        "how am i doing", "help me save", "reduce spend", "increase savings"
    ]
    
    return any(pattern in text_lower for pattern in insight_patterns)


# Preserve legacy import compatibility if needed
def route_intent(message, *, psid_hash, now, ai, db):
    """Legacy compatibility wrapper - routes to production router"""
    from utils.production_router import ProductionRouter
    router = ProductionRouter()
    return router.route_message(message, psid_hash, "")


def route_intent_v2(*args, **kwargs):
    """Alternative legacy compatibility wrapper"""
    return route_intent(*args, **kwargs)