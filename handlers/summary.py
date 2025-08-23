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
        
        # Generate AI summary reply
        from templates.replies_ai import format_ai_summary_reply, log_reply_banner
        log_reply_banner('SUMMARY', user_id)
        
        if not expenses:
            return {"text": format_ai_summary_reply(period, 0, 0, [])}
        
        # Calculate totals
        total_amount = sum(exp.total for exp in expenses)
        total_entries = sum(exp.count for exp in expenses)
        
        # Build category list
        categories = [exp.category for exp in expenses[:5]]  # Top 5 categories
        
        # Use AI template
        msg = format_ai_summary_reply(period, total_amount, total_entries, categories)
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Summary handler error: {e}")
        return {"text": "Unable to generate summary. Please try again later."}