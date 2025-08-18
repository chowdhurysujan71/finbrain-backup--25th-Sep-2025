"""
Summary handler: Provides expense summaries without AI
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

def month_bounds(now=None, tz=timezone.utc) -> Tuple[datetime, datetime]:
    """Get start and end of current month"""
    now = now or datetime.now(tz)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year+1, month=1)
    else:
        end = start.replace(month=start.month+1)
    return start, end

def week_bounds(now=None, tz=timezone.utc) -> Tuple[datetime, datetime]:
    """Get start and end of current week"""
    now = now or datetime.now(tz)
    start = now - timedelta(days=7)
    return start, now

def handle_summary(user_id: str, timeframe: str = "week") -> Dict[str, str]:
    """
    Generate expense summary for user
    Returns dict with 'text' key containing the summary message
    """
    try:
        from models import Expense
        from app import db
        
        # Get appropriate time bounds
        if timeframe == "month":
            start, end = month_bounds()
            period = "this month"
        else:
            start, end = week_bounds()
            period = "last 7 days"
        
        # Query expenses
        expenses = db.session.query(
            Expense.category,
            db.func.sum(Expense.amount).label('total'),
            db.func.count(Expense.id).label('count')
        ).filter(
            Expense.user_id == user_id,
            Expense.created_at >= start,
            Expense.created_at < end
        ).group_by(Expense.category).all()
        
        if not expenses:
            return {"text": f"No expenses logged for {period}. Start tracking with 'spent 100 on lunch'."}
        
        # Calculate totals
        total_amount = sum(exp.total for exp in expenses)
        total_entries = sum(exp.count for exp in expenses)
        
        # Build category breakdown
        categories = []
        for exp in expenses[:5]:  # Top 5 categories
            pct = (exp.total / total_amount) * 100 if total_amount > 0 else 0
            categories.append(f"{exp.category}: {exp.total:.0f} ({pct:.0f}%)")
        
        # Format message
        msg = f"📊 {period.capitalize()}: {total_amount:.0f} BDT across {total_entries} entries.\n"
        if categories:
            msg += "Categories:\n" + "\n".join(f"• {cat}" for cat in categories)
        
        msg += "\n\nTip: type 'insight' for spending optimization tips."
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Summary handler error: {e}")
        return {"text": "Unable to generate summary. Please try again later."}