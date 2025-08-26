"""
Insight handler: Provides spending insights and recommendations without AI
"""
from typing import Dict
import logging
from .summary import month_bounds

logger = logging.getLogger(__name__)

def handle_insight(user_id: str) -> Dict[str, str]:
    """
    Generate AI-powered spending insights and recommendations
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
        
        # Try AI-powered insights first
        try:
            from utils.ai_adapter_v2 import production_ai_adapter
            ai_adapter = production_ai_adapter
            
            # Prepare data for AI
            expense_data = []
            for exp in expenses:
                pct = (exp.total / total) * 100
                expense_data.append({
                    'category': exp.category,
                    'total': float(exp.total),
                    'percentage': pct
                })
            
            expenses_context = {
                'total_amount': total,
                'expenses': expense_data,
                'timeframe': 'this month',
                'expense_count': len(expenses)
            }
            
            # Generate AI insights
            ai_result = ai_adapter.generate_insights(expenses_context)
            
            if ai_result.get('success'):
                insights = ai_result.get('insights', [])
                if insights:
                    # Use AI-generated insights
                    msg = format_ai_insight_reply(insights, total)
                    logger.info(f"AI insights generated successfully for {user_id[:8]}...")
                    return {"text": msg}
            
            # Log AI failure reason for debugging
            logger.warning(f"AI insights failed: {ai_result.get('reason', 'unknown')}")
            
        except Exception as ai_error:
            logger.warning(f"AI insights error, falling back to rules: {ai_error}")
        
        # Fallback to rule-based insights if AI fails
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
        
        # Use fallback template
        if not insights:
            insights = ["Your spending looks balanced!", "Great job tracking your expenses"]
            
        msg = format_ai_insight_reply(insights, total)
        logger.info(f"Rule-based insights generated for {user_id[:8]}...")
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Insight handler error: {e}")
        return {"text": "Unable to generate insights. Please try again later."}