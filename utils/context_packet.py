"""
Context packet system for data-driven AI responses
Builds user-specific spending snapshots and enforces numeric advice with guard logic
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import Expense, User
from .identity import psid_hash

logger = logging.getLogger(__name__)

def build_context(psid: str, db: Session) -> Dict[str, Any]:
    """
    Build structured context packet for AI with 30-day spending patterns, trends, and goals
    
    Args:
        psid: Facebook Page-Scoped ID
        db: Database session
        
    Returns:
        Dict with income, spending by category, deltas, recurring expenses, goals
    """
    try:
        user_hash = psid_hash(psid)
        now = datetime.utcnow()
        
        # Get 30-day and previous 30-day spending by category
        by_cat_30d = get_spend_by_category(db, user_hash, days=30)
        by_cat_prev30 = get_spend_by_category(db, user_hash, days=60, days_end=31)
        
        # Get income data (placeholder - would integrate with income tracking)
        income_month = get_income(db, user_hash, days=30)
        
        # Get recurring expenses and goals (placeholder - would integrate with goal system)
        recurrences = get_recurring_expenses(db, user_hash)
        goals = get_user_goals(db, user_hash)
        
        # Compute category deltas vs previous period
        cur = {c: a for c, a in by_cat_30d}
        prev = {c: a for c, a in by_cat_prev30}
        
        deltas = []
        for category in cur:
            current_amount = cur[category]
            previous_amount = prev.get(category, 0)
            if previous_amount > 0:
                delta_pct = int(round(100 * (current_amount - previous_amount) / previous_amount))
            else:
                delta_pct = 100 if current_amount > 0 else 0
            deltas.append((category, int(current_amount), delta_pct))
        
        # Sort by spending amount, top 5 categories
        top_cats = sorted(deltas, key=lambda x: x[1], reverse=True)[:5]
        
        context = {
            "income_30d": int(income_month or 0),
            "top_cats": [
                {"category": c, "amount": a, "delta_pct": d} 
                for c, a, d in top_cats
            ],
            "total_spend_30d": int(sum(cur.values())),
            "recurring": [
                {"name": n, "amount": int(a), "day": d} 
                for n, a, d in recurrences
            ][:8],
            "goals": [
                {"name": n, "current": int(current), "target": int(target)} 
                for n, current, target in goals
            ][:5],
            "context_quality": "rich" if len(top_cats) >= 2 and sum(cur.values()) > 0 else "thin"
        }
        
        logger.info(f"Context built for {psid[:8]}...: {len(top_cats)} categories, ৳{context['total_spend_30d']:,} total")
        return context
        
    except Exception as e:
        logger.error(f"Context building failed for {psid[:8]}...: {e}")
        return {
            "income_30d": 0,
            "top_cats": [],
            "total_spend_30d": 0,
            "recurring": [],
            "goals": [],
            "context_quality": "thin"
        }

def get_spend_by_category(db: Session, user_hash: str, days: int, days_end: int = 0) -> List[Tuple[str, float]]:
    """Get spending by category for specified date range"""
    try:
        end_date = datetime.utcnow() - timedelta(days=days_end)
        start_date = end_date - timedelta(days=days)
        
        expenses = db.query(Expense).filter(
            Expense.user_id == user_hash,
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        ).all()
        
        # Group by category
        by_category = {}
        for expense in expenses:
            category = expense.category or 'other'
            by_category[category] = by_category.get(category, 0) + expense.amount
        
        return list(by_category.items())
        
    except Exception as e:
        logger.error(f"Category spending query failed: {e}")
        return []

def get_income(db: Session, user_hash: str, days: int) -> Optional[float]:
    """Get income data for specified period (placeholder implementation)"""
    try:
        # TODO: Implement income tracking table
        # For now, return None to indicate no income data
        return None
    except Exception as e:
        logger.error(f"Income query failed: {e}")
        return None

def get_recurring_expenses(db: Session, user_hash: str) -> List[Tuple[str, float, int]]:
    """Get recurring expenses (placeholder implementation)"""
    try:
        # TODO: Implement recurring expense detection/tracking
        # For now, analyze expense patterns to identify potential recurring items
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)
        
        expenses = db.query(Expense).filter(
            Expense.user_id == user_hash,
            Expense.created_at >= start_date,
            Expense.created_at <= end_date
        ).all()
        
        # Simple heuristic: look for similar amounts/descriptions
        recurring_candidates = []
        
        # Group by category and look for consistent amounts
        category_amounts = {}
        for expense in expenses:
            category = expense.category or 'other'
            if category not in category_amounts:
                category_amounts[category] = []
            category_amounts[category].append(expense.amount)
        
        # Find categories with consistent spending (potential recurring)
        for category, amounts in category_amounts.items():
            if len(amounts) >= 3:  # At least 3 transactions
                avg_amount = sum(amounts) / len(amounts)
                # If amounts are relatively consistent (within 20% of average)
                consistent = sum(1 for a in amounts if abs(a - avg_amount) / avg_amount <= 0.2)
                if consistent >= len(amounts) * 0.6:  # 60% of transactions are consistent
                    day_of_month = 1  # Placeholder - would analyze actual dates
                    recurring_candidates.append((category.title(), avg_amount, day_of_month))
        
        return recurring_candidates[:5]  # Top 5 recurring candidates
        
    except Exception as e:
        logger.error(f"Recurring expenses query failed: {e}")
        return []

def get_user_goals(db: Session, user_hash: str) -> List[Tuple[str, float, float]]:
    """Get user financial goals (placeholder implementation)"""
    try:
        # TODO: Implement goals tracking table
        # For now, return empty list
        return []
    except Exception as e:
        logger.error(f"Goals query failed: {e}")
        return []

def is_context_thin(context: Dict[str, Any]) -> bool:
    """
    Determine if context is too thin for personalized advice
    
    Args:
        context: Context packet from build_context()
        
    Returns:
        True if context is thin (should refuse generic advice)
    """
    return (
        context["total_spend_30d"] == 0 or 
        len(context["top_cats"]) < 2 or
        context.get("context_quality") == "thin"
    )

def get_thin_context_reply() -> Tuple[str, List[Dict[str, str]]]:
    """
    Get reply for when context is too thin for personalized advice
    
    Returns:
        (message_text, quick_reply_options)
    """
    message = "I don't see enough recent spend to personalize that."
    quick_replies = [
        {"title": "Log 3 spends now", "payload": "LOG_3"},
        {"title": "Import last month", "payload": "IMPORT_CSV"},
        {"title": "Set a goal", "payload": "SET_GOAL"},
    ]
    return message, quick_replies

# System prompt for context-driven AI responses
CONTEXT_SYSTEM_PROMPT = """
You are a personable financial coach.
Use ONLY the provided user_context for numeric advice.
If user_context is empty or too thin (<2 categories), DO NOT generalize.
Instead, ask for one high-leverage action to collect data (e.g., 'log 3 biggest spends today' or 'connect bank export').
Replies: 2–3 short sentences max. Give one next step and one question.
"""

# JSON schema for structured AI responses
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Brief spending analysis with specific numbers"},
        "action": {"type": "string", "description": "Specific next step recommendation"},
        "question": {"type": "string", "description": "Single follow-up question"}
    },
    "required": ["summary", "action", "question"]
}

def format_context_for_ai(context: Dict[str, Any]) -> str:
    """
    Format context packet for AI consumption
    
    Args:
        context: Context packet from build_context()
        
    Returns:
        Formatted string for AI prompt
    """
    if is_context_thin(context):
        return "user_context={\"status\": \"insufficient_data\"}"
    
    # Format rich context for AI
    formatted = f"""user_context={{
    "income_30d": {context['income_30d']},
    "total_spend_30d": {context['total_spend_30d']},
    "top_categories": {context['top_cats']},
    "recurring_expenses": {context['recurring']},
    "goals": {context['goals']}
}}"""
    
    return formatted

# Test function
def test_context_packet():
    """Test context packet system with mock data"""
    print("=== CONTEXT PACKET SYSTEM TEST ===")
    
    # Test thin context detection
    thin_context = {
        "income_30d": 0,
        "top_cats": [],
        "total_spend_30d": 0,
        "recurring": [],
        "goals": [],
        "context_quality": "thin"
    }
    
    rich_context = {
        "income_30d": 55000,
        "top_cats": [
            {"category": "dining", "amount": 8240, "delta_pct": 18},
            {"category": "groceries", "amount": 12500, "delta_pct": -5},
            {"category": "transport", "amount": 3200, "delta_pct": 25}
        ],
        "total_spend_30d": 42600,
        "recurring": [
            {"name": "rent", "amount": 15000, "day": 1},
            {"name": "utilities", "amount": 2500, "day": 5}
        ],
        "goals": [
            {"name": "emergency_fund", "current": 25000, "target": 100000}
        ],
        "context_quality": "rich"
    }
    
    print(f"Thin context detection: {is_context_thin(thin_context)}")
    print(f"Rich context detection: {is_context_thin(rich_context)}")
    
    # Test thin context reply
    message, replies = get_thin_context_reply()
    print(f"Thin context reply: {message}")
    print(f"Quick replies: {[r['title'] for r in replies]}")
    
    # Test AI context formatting
    ai_context = format_context_for_ai(rich_context)
    print(f"AI context format: {ai_context[:100]}...")
    
    print("✅ Context packet system tested successfully")

if __name__ == "__main__":
    test_context_packet()