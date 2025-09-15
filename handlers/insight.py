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
        from db_base import db
        
        start, end = month_bounds()
        
        # Get expense breakdown
        expenses = db.session.query(
            Expense.category,
            db.func.sum(Expense.amount).label('total')
        ).filter(
            Expense.user_id_hash == user_id,
            Expense.created_at >= start,
            Expense.created_at < end
        ).group_by(Expense.category).order_by(db.desc('total')).all()
        
        # BLOCK 4 ANALYTICS: Track report request (fail-safe)
        try:
            from utils.analytics_engine import track_report_request
            from models import User
            user = db.session.query(User).filter_by(user_id_hash=user_id).first()
            if user:
                track_report_request(user, "insight_command")
        except Exception as e:
            logger.debug(f"Report analytics tracking failed: {e}")
        
        # Generate AI insights reply
        from templates.replies_ai import format_ai_insight_reply, log_reply_banner
        log_reply_banner('INSIGHT', user_id)
        
        if not expenses:
            return {"text": format_ai_insight_reply([], 0, "this month")}
        
        total = sum(exp.total for exp in expenses)
        
        # Try AI-powered insights first
        try:
            from utils.ai_adapter_v2 import production_ai_adapter
            ai_adapter = production_ai_adapter
            
            # Prepare data for AI with request uniqueness
            import time
            expense_data = []
            for exp in expenses:
                pct = (exp.total / total) * 100
                expense_data.append({
                    'category': exp.category,
                    'total': float(exp.total),
                    'percentage': pct
                })
            
            # Add request uniqueness to prevent AI response caching
            import time
            import random
            request_uniqueness = f"{user_id}_{int(time.time())}_{random.randint(1000,9999)}"
            
            # Get recent activity context (last 7 days)
            from datetime import datetime, timedelta
            week_start = datetime.now() - timedelta(days=7)
            
            recent_expenses = db.session.query(
                Expense.category,
                db.func.sum(Expense.amount).label('total'),
                db.func.count(Expense.id).label('count')
            ).filter(
                Expense.user_id_hash == user_id,
                Expense.created_at >= week_start
            ).group_by(Expense.category).all()
            
            recent_total = sum(exp.total for exp in recent_expenses) if recent_expenses else 0
            recent_categories = [{'category': exp.category, 'total': float(exp.total), 'count': exp.count} 
                               for exp in recent_expenses] if recent_expenses else []
            
            expenses_context = {
                'total_amount': total,
                'expenses': expense_data,
                'timeframe': 'this month',
                'expense_count': len(expenses),
                'recent_activity': {
                    'last_7_days_total': recent_total,
                    'last_7_days_categories': recent_categories,
                    'recent_vs_monthly_ratio': (recent_total / total * 100) if total > 0 else 0
                },
                'request_id': request_uniqueness,
                'user_context': f"user_{user_id[:8]}_insights",
                'timestamp': time.time()
            }
            
            # Generate AI insights with user isolation
            ai_result = ai_adapter.generate_insights(expenses_context, user_id)
            
            if ai_result.get('success'):
                insights = ai_result.get('insights', [])
                if insights:
                    # Use AI-generated insights with timeframe
                    msg = format_ai_insight_reply(insights, total, "this month")
                    logger.info(f"AI insights generated successfully for {user_id[:8]}...")
                    return {"text": msg}
            
            # Log AI failure reason for debugging
            logger.warning(f"AI insights failed: {ai_result.get('reason', 'unknown')}")
            
        except Exception as ai_error:
            logger.warning(f"AI insights error, falling back to rules: {ai_error}")
        
        # Generate engaging, human-like insights when AI fails
        insights = []
        import random
        
        for exp in expenses:
            pct = (exp.total / total) * 100
            category_lower = exp.category.lower()
            
            # ENGAGING food insights with variety
            if category_lower in {"groceries", "food"} and pct > 30:
                food_insights = [
                    f"Food's taking {pct:.0f}% of your budget! 🍽️ Maybe try cooking one extra meal at home this week?",
                    f"Noticed food is {pct:.0f}% of spending - what if you tried batch cooking this weekend?",
                    f"Food lovers unite! {pct:.0f}% goes to meals. Try the 'cook twice, eat thrice' approach?",
                    f"Food is {pct:.0f}% - totally normal! Consider prepping snacks to avoid impulse food buys",
                    f"Your {pct:.0f}% food spending shows you eat well! Maybe try one homemade lunch per week?"
                ]
                insights.append(random.choice(food_insights))
                
            # ENGAGING transport insights
            elif category_lower in {"ride", "transport", "uber", "taxi"} and pct > 20:
                transport_insights = [
                    f"Transport's {pct:.0f}% of your budget - consider combining errands into one trip?",
                    f"Getting around costs {pct:.0f}%! What about trying public transport for short trips?",
                    f"Travel expenses at {pct:.0f}% - maybe walk to nearby places when the weather's nice?",
                    f"{pct:.0f}% on transport! Try ride-sharing apps during off-peak hours for better rates",
                    f"Movement is {pct:.0f}% of spending - consider a monthly transit pass if you ride often?"
                ]
                insights.append(random.choice(transport_insights))
                
            # ENGAGING shopping insights  
            elif category_lower in {"shopping", "clothes"} and pct > 25:
                shopping_insights = [
                    f"Shopping therapy taking {pct:.0f}%? Try the 24-hour rule before buying non-essentials",
                    f"Retail at {pct:.0f}%! What about making a wishlist before shopping trips?",
                    f"Shopping's {pct:.0f}% - maybe check your closet first before buying new clothes?",
                    f"{pct:.0f}% on shopping! Consider the 'one in, one out' rule for new purchases",
                    f"Spending {pct:.0f}% shopping - try browsing online first to compare prices?"
                ]
                insights.append(random.choice(shopping_insights))
                
            # ENGAGING entertainment insights
            elif category_lower in {"entertainment", "fun"} and pct > 15:
                fun_insights = [
                    f"Fun spending at {pct:.0f}%! Life's about balance - maybe mix in some free activities?",
                    f"Entertainment is {pct:.0f}% - what about exploring free museums or parks this month?",
                    f"Having fun costs {pct:.0f}%! Try hosting friends at home instead of going out sometimes?",
                    f"{pct:.0f}% on entertainment - consider happy hour prices or matinee shows?",
                    f"Fun budget is {pct:.0f}%! Look for free community events or outdoor activities?"
                ]
                insights.append(random.choice(fun_insights))
        
        # DYNAMIC fallback insights with personality
        if not insights:
            balanced_insights = [
                f"Looking good! ৳{total:,.0f} spread nicely across {len(expenses)} categories. Your spending's got balance! 💚",
                f"Nice work! ৳{total:,.0f} this month shows you're being mindful. Keep up the awareness! 🌟",
                f"Solid spending pattern! ৳{total:,.0f} across categories - you're staying conscious of your money 📊",
                f"Your ৳{total:,.0f} monthly spend looks thoughtful. Love seeing this level of tracking! ✨",
                f"Great balance! ৳{total:,.0f} distributed well. You're building excellent money habits 💪"
            ]
            insights = [random.choice(balanced_insights)]
            
        msg = format_ai_insight_reply(insights, total)
        logger.info(f"Rule-based insights generated for {user_id[:8]}...")
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Insight handler error: {e}")
        return {"text": "Unable to generate insights. Please try again later."}