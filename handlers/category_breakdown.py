"""
Category Breakdown Handler
Handles specific category expense queries like "How much did I spend on food this month?"
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def extract_category_from_query(text: str) -> Optional[str]:
    """Extract category name from user query"""
    text_lower = text.lower().strip()
    
    # Category mapping - maps user words to our database categories
    category_map = {
        # Food categories
        "food": "food", "foods": "food", "eating": "food", "meals": "food",
        "groceries": "food", "grocery": "food", "dining": "food", "restaurant": "food",
        "restaurants": "food", "lunch": "food", "dinner": "food", "breakfast": "food",
        "coffee": "food", "snacks": "food", "drinks": "food",
        
        # Transport categories  
        "transport": "transport", "transportation": "transport", "travel": "transport",
        "rides": "transport", "ride": "transport", "riding": "transport",
        "uber": "transport", "taxi": "transport", "bus": "transport", "train": "transport",
        "gas": "transport", "fuel": "transport", "parking": "transport",
        
        # Shopping categories
        "shopping": "shopping", "clothes": "shopping", "clothing": "shopping",
        "amazon": "shopping", "online": "shopping", "store": "shopping",
        
        # Entertainment
        "entertainment": "entertainment", "movie": "entertainment", "movies": "entertainment",
        "games": "entertainment", "cinema": "entertainment",
        
        # Bills and utilities
        "bills": "bills", "bill": "bills", "utilities": "bills", "utility": "bills",
        "rent": "bills", "housing": "bills", "internet": "bills", "phone": "bills",
        
        # Health
        "health": "health", "medical": "health", "pharmacy": "health", "doctor": "health",
        "medicine": "health", "hospital": "health"
    }
    
    # Find the category mentioned in the text
    for word, category in category_map.items():
        if word in text_lower:
            return category
    
    return None

def extract_timeframe_from_query(text: str) -> str:
    """Extract timeframe from user query, default to current month"""
    text_lower = text.lower().strip()
    
    if "this week" in text_lower or "last 7 days" in text_lower:
        return "week"
    elif "last week" in text_lower:
        return "last_week"  
    elif "this month" in text_lower:
        return "month"
    elif "last month" in text_lower:
        return "last_month"
    elif "today" in text_lower:
        return "today"
    elif "yesterday" in text_lower:
        return "yesterday"
    else:
        # Default to current month for category queries
        return "month"

def get_timeframe_bounds(timeframe: str) -> Tuple[datetime, datetime]:
    """Get start and end datetime for the specified timeframe"""
    now = datetime.now(timezone.utc)
    
    if timeframe == "week":
        start = now - timedelta(days=7)
        end = now
    elif timeframe == "last_week":
        end = now - timedelta(days=7)
        start = end - timedelta(days=7)
    elif timeframe == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif timeframe == "last_month":
        # Get first day of current month
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Go back one month for end
        if current_month_start.month == 1:
            end = current_month_start
            start = end.replace(year=end.year-1, month=12)
        else:
            end = current_month_start
            start = end.replace(month=end.month-1)
    elif timeframe == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif timeframe == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    else:
        # Default to current month
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    
    return start, end

def handle_category_breakdown(user_id: str, text: str) -> Dict[str, str]:
    """
    Handle category-specific breakdown queries
    Returns dict with 'text' key containing the response
    """
    try:
        from models import Expense
        from app import app, db
        from sqlalchemy import func
        
        # Extract category and timeframe from query
        category = extract_category_from_query(text)
        timeframe = extract_timeframe_from_query(text)
        
        if not category:
            return {"text": "I couldn't identify which category you're asking about. Try asking like 'How much did I spend on food this month?'"}
        
        # Get time bounds
        start, end = get_timeframe_bounds(timeframe)
        
        # Format timeframe for response
        timeframe_text = {
            "week": "this week",
            "last_week": "last week", 
            "month": "this month",
            "last_month": "last month",
            "today": "today",
            "yesterday": "yesterday"
        }.get(timeframe, "this month")
        
        with app.app_context():
            # For transport category, search for both "transport" and "ride" categories
            if category == "transport":
                category_filter = (
                    Expense.category.ilike('%transport%') |
                    Expense.category.ilike('%ride%') |
                    Expense.category.ilike('%taxi%') |
                    Expense.category.ilike('%uber%')
                )
            else:
                category_filter = Expense.category.ilike(f"%{category}%")
            
            # Query expenses for the specific category and timeframe
            result = db.session.query(
                func.coalesce(func.sum(Expense.amount), 0).label('total'),
                func.count(Expense.id).label('count')
            ).filter(
                Expense.user_id_hash == user_id,
                category_filter,
                Expense.created_at >= start,
                Expense.created_at < end
            ).first()
            
            total_amount = float(result.total) if result and result.total else 0
            transaction_count = int(result.count) if result and result.count else 0
            
            # Generate natural response with variation
            return generate_category_response(category, timeframe_text, total_amount, transaction_count)
            
    except Exception as e:
        logger.error(f"Category breakdown failed: {e}")
        return {"text": "I had trouble getting that breakdown. Try asking for your regular summary instead!"}

def generate_category_response(category: str, timeframe: str, amount: float, count: int) -> Dict[str, str]:
    """Generate natural, varied responses for category breakdowns"""
    import random
    
    # Format amount
    if amount == 0:
        # No expenses found variations
        no_expense_responses = [
            f"Great news! You haven't spent anything on {category} {timeframe}. 🎉",
            f"No {category} expenses {timeframe} - your wallet thanks you! 💚",
            f"Zero spent on {category} {timeframe}. You're doing amazing! ✨",
            f"Looks like you skipped {category} expenses {timeframe}. Well done! 👏",
            f"No {category} spending {timeframe} - that's some impressive discipline! 🌟"
        ]
        response = random.choice(no_expense_responses)
        
    else:
        # Format currency
        formatted_amount = f"৳{amount:,.0f}"
        
        # Transaction count context
        if count == 1:
            count_text = "in 1 transaction"
        else:
            count_text = f"across {count} transactions"
        
        # Main response variations
        main_responses = [
            f"You spent {formatted_amount} on {category} {timeframe} ({count_text})",
            f"Your {category} spending {timeframe}: {formatted_amount} {count_text}",
            f"{formatted_amount} went to {category} {timeframe} - {count_text}",
            f"Total {category} expenses {timeframe}: {formatted_amount} {count_text}",
            f"Here's your {category} breakdown {timeframe}: {formatted_amount} {count_text}"
        ]
        
        response = random.choice(main_responses)
        
        # Add context and tips for larger amounts
        if amount > 3000:
            tips = [
                " That's quite a bit - want some tips to optimize this category?",
                " Want insights on how to reduce this next month?", 
                " Interested in seeing patterns to save money here?",
                " Looking to trim this down? I can share some ideas!",
                " Want suggestions to optimize your spending in this area?"
            ]
            response += random.choice(tips)
        elif amount > 1000:
            moderate_tips = [
                " Not bad! Want to see how this compares to last month?",
                " Pretty reasonable! Interested in tracking trends?",
                " Solid control! Want insights for further optimization?",
                " Good spending discipline! Check back anytime for updates."
            ]
            response += random.choice(moderate_tips)
    
    # Add friendly closing
    closings = [
        " Feel free to check back anytime! 😊",
        " Hope that helps - let me know if you need anything else!",
        " Thanks for tracking your expenses! Check in again soon.",
        " Keep up the great financial awareness! 💪",
        " Hope this breakdown was helpful! See you next time.",
        " Always here when you need spending insights! 🚀"
    ]
    
    response += random.choice(closings)
    
    return {"text": response}