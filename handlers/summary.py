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

def get_previous_period_data(user_id: str, timeframe: str = "week") -> Tuple[float, str]:
    """
    Get spending data from previous period for comparison
    Returns (total_amount, top_category)
    """
    try:
        from models import Expense
        from app import db
        
        now = datetime.now(timezone.utc)
        
        if timeframe == "month":
            # Get last month's data
            if now.month == 1:
                prev_month = 12
                prev_year = now.year - 1
            else:
                prev_month = now.month - 1
                prev_year = now.year
            
            start = datetime(prev_year, prev_month, 1, tzinfo=timezone.utc)
            if prev_month == 12:
                end = datetime(prev_year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end = datetime(prev_year, prev_month + 1, 1, tzinfo=timezone.utc)
        else:
            # Get previous week's data (14-7 days ago)
            end = now - timedelta(days=7)
            start = end - timedelta(days=7)
        
        # Query using existing field name
        expenses = db.session.query(
            db.func.sum(Expense.amount).label('total'),
            Expense.category
        ).filter(
            Expense.user_id == user_id,
            Expense.created_at >= start,
            Expense.created_at < end
        ).group_by(Expense.category).all()
        
        if not expenses:
            return 0.0, ""
        
        # Calculate total and find top category
        total = sum(float(exp.total or 0) for exp in expenses)
        top_category = max(expenses, key=lambda x: float(x.total or 0)).category if expenses else ""
        
        return total, top_category
        
    except Exception as e:
        logger.error(f"Error getting previous period data: {e}")
        return 0.0, ""

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
        
        # Get previous period comparison data
        prev_total, prev_top_category = get_previous_period_data(user_id, timeframe)
        
        # Calculate comparison data
        comparison_data = None
        if prev_total > 0 and total_amount > 0:
            # Ensure both values are floats for calculation
            current_total_float = float(total_amount)
            prev_total_float = float(prev_total)
            change_pct = ((current_total_float - prev_total_float) / prev_total_float) * 100
            comparison_data = {
                'change_pct': change_pct,
                'prev_total': prev_total_float,
                'timeframe': timeframe
            }
        
        # Use AI template with comparison data
        msg = format_ai_summary_reply(period, total_amount, total_entries, categories, comparison_data)
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Summary handler error: {e}")
        return {"text": "Unable to generate summary. Please try again later."}