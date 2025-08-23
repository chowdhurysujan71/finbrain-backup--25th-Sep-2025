"""
Insight handler: Provides spending insights and recommendations without AI
"""
from typing import Dict
import logging
from .summary import month_bounds

logger = logging.getLogger(__name__)

def handle_insight(user_id: str) -> Dict[str, str]:
    """
    Generate spending insights and recommendations
    Returns dict with 'text' key containing insights
    """
    try:
        from models import Expense
        from app import db
        
        start, end = month_bounds()
        
        # Get expense breakdown
        expenses = db.session.query(
            Expense.category,
            db.func.sum(Expense.amount).label('total')
        ).filter(
            Expense.user_id == user_id,
            Expense.created_at >= start,
            Expense.created_at < end
        ).group_by(Expense.category).order_by(db.desc('total')).all()
        
        # Generate AI insights reply
        from templates.replies_ai import format_ai_insight_reply, log_reply_banner
        log_reply_banner('INSIGHT', user_id)
        
        if not expenses:
            return {"text": format_ai_insight_reply([], 0)}
        
        total = sum(exp.total for exp in expenses)
        
        # Generate recommendations based on spending patterns
        insights = []
        for exp in expenses:
            pct = (exp.total / total) * 100
            category_lower = exp.category.lower()
            
            # Rule-based recommendations
            if category_lower in {"groceries", "food"} and pct > 30:
                insights.append(f"Food spending is {pct:.0f}% - consider meal planning to reduce by 10%")
            elif category_lower in {"ride", "transport", "uber", "taxi"} and pct > 20:
                insights.append(f"Transport is {pct:.0f}% - try batching trips or using off-peak times")
            elif category_lower in {"shopping", "clothes"} and pct > 25:
                insights.append(f"Shopping is {pct:.0f}% - set a monthly budget limit")
            elif category_lower in {"entertainment", "fun"} and pct > 15:
                insights.append(f"Entertainment is {pct:.0f}% - look for free activities")
        
        # Use AI template
        msg = format_ai_insight_reply(insights, total)
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Insight handler error: {e}")
        return {"text": "Unable to generate insights. Please try again later."}