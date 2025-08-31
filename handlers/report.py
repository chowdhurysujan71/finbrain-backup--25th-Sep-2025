"""
Money Story Report Handler - Generates gamified financial narratives
"""

import logging
from typing import Dict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


def handle_report(user_id: str) -> Dict[str, str]:
    """
    Generate Money Story report for user with feedback collection
    Returns dict with 'text' key containing the narrative report + feedback prompt
    """
    try:
        from models import Expense
        from app import db
        from utils.feedback_context import set_feedback_context
        import uuid
        
        # Emit telemetry event
        _emit_telemetry_event(user_id)
        
        # Determine time window (3-day challenge vs 7-day default)
        days_window = _get_time_window(user_id)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days_window)
        
        # Query expenses for the time window
        expenses = db.session.query(Expense).filter(
            Expense.user_id_hash == user_id,
            Expense.created_at >= start_time,
            Expense.created_at <= end_time
        ).all()
        
        # Generate Money Story
        story = _generate_money_story(expenses, days_window, user_id)
        
        # Phase 2: Add feedback collection
        try:
            # Generate unique context ID for this report
            report_context_id = f"report_{int(datetime.now().timestamp())}_{str(uuid.uuid4())[:8]}"
            
            # Set feedback context
            set_feedback_context(user_id, report_context_id)
            
            # Add feedback prompt to story
            feedback_prompt = "\n\n💭 Was this helpful? Reply YES or NO"
            enhanced_story = story + feedback_prompt
            
            logger.info(f"Generated Money Story with feedback prompt for user {user_id[:8]}... (context: {report_context_id})")
            return {"text": enhanced_story}
            
        except Exception as feedback_error:
            # Feedback system failure should not break reports
            logger.warning(f"Feedback context setup failed: {feedback_error}, returning story without prompt")
            return {"text": story}
        
    except Exception as e:
        logger.error(f"Report handler error: {e}")
        return {"text": "Unable to generate your money story right now. Please try again later."}


def _get_time_window(user_id: str) -> int:
    """
    Determine time window based on 3-day challenge status
    Returns 3 if user has active challenge, 7 otherwise
    """
    try:
        # TODO: Check for 3-day challenge status
        # For now, default to 7 days
        # In future: query challenge status from database
        return 7
    except:
        return 7  # Safe fallback


def _generate_money_story(expenses, days_window: int, user_id: str) -> str:
    """
    Generate narrative Money Story from expense data
    Maximum 500 characters, 4-6 sentences
    """
    try:
        if not expenses:
            return f"No expenses logged in the last {days_window} days. Start tracking to see your money story unfold!"
        
        # Calculate basic stats
        total_logs = len(expenses)
        total_amount = sum(float(expense.amount) for expense in expenses)
        
        # Calculate category breakdown
        categories = {}
        for expense in expenses:
            cat = expense.category or "other"
            categories[cat] = categories.get(cat, 0) + float(expense.amount)
        
        # Find top category
        if categories:
            top_category = max(categories.keys(), key=lambda k: categories[k])
            top_percentage = int((categories[top_category] / total_amount) * 100) if total_amount > 0 else 0
        else:
            top_category = "general"
            top_percentage = 0
        
        # Check for wins (compare with previous period)
        win_text = _find_spending_win(expenses, days_window, user_id)
        
        # Check streak
        streak_text = _get_streak_text(user_id)
        
        # Generate next-step tip
        tip = _get_next_step_tip(categories, total_logs)
        
        # Compose story (4-6 sentences, ≤500 chars)
        story_parts = []
        
        # Core stats
        story_parts.append(f"You logged {total_logs} expenses totaling ৳{total_amount:.0f} in the last {days_window} days.")
        
        # Top category
        if top_percentage > 0:
            story_parts.append(f"{top_category.title()} took {top_percentage}% of your spending.")
        
        # Win or neutral observation
        if win_text:
            story_parts.append(win_text)
        else:
            story_parts.append("Your spending patterns are taking shape.")
        
        # Streak mention if ≥3
        if streak_text:
            story_parts.append(streak_text)
        
        # Tip
        story_parts.append(tip)
        
        # Join and ensure ≤500 characters
        story = " ".join(story_parts)
        if len(story) > 500:
            # Truncate gracefully
            story = story[:497] + "..."
        
        return story
        
    except Exception as e:
        logger.error(f"Money story generation error: {e}")
        return f"Tracked {len(expenses)} expenses in {days_window} days. Keep logging to see detailed patterns!"


def _find_spending_win(expenses, days_window: int, user_id: str) -> str:
    """Find a spending win by comparing with previous period"""
    try:
        from models import Expense
        from app import db
        
        # Get previous period expenses
        end_time = datetime.now(timezone.utc) - timedelta(days=days_window)
        start_time = end_time - timedelta(days=days_window)
        
        prev_expenses = db.session.query(Expense).filter(
            Expense.user_id_hash == user_id,
            Expense.created_at >= start_time,
            Expense.created_at <= end_time
        ).all()
        
        if not prev_expenses:
            return ""  # No comparison data
        
        # Compare categories
        current_cats = {}
        for exp in expenses:
            cat = exp.category or "other"
            current_cats[cat] = current_cats.get(cat, 0) + float(exp.amount)
        
        prev_cats = {}
        for exp in prev_expenses:
            cat = exp.category or "other"
            prev_cats[cat] = prev_cats.get(cat, 0) + float(exp.amount)
        
        # Find biggest improvement
        for category, current_amount in current_cats.items():
            prev_amount = prev_cats.get(category, 0)
            if prev_amount > 0:
                reduction = ((prev_amount - current_amount) / prev_amount) * 100
                if reduction >= 15:  # 15% reduction threshold
                    return f"Great job reducing {category} spending by {reduction:.0f}% vs last period! 🏆"
        
        return ""  # No significant wins found
        
    except Exception as e:
        logger.debug(f"Win detection error: {e}")
        return ""


def _get_streak_text(user_id: str) -> str:
    """Get streak text if streak ≥ 3 days"""
    try:
        from models import Expense
        from app import db
        
        # Calculate consecutive logging days
        today = datetime.now(timezone.utc).date()
        streak_days = 0
        check_date = today
        
        for i in range(30):  # Check up to 30 days back
            expenses_on_date = db.session.query(Expense).filter(
                Expense.user_id_hash == user_id,
                db.func.date(Expense.created_at) == check_date
            ).count()
            
            if expenses_on_date > 0:
                streak_days += 1
                check_date -= timedelta(days=1)
            else:
                break
        
        if streak_days >= 3:
            return f"🔥 You're on a {streak_days}-day logging streak!"
        
        return ""
        
    except Exception as e:
        logger.debug(f"Streak calculation error: {e}")
        return ""


def _get_next_step_tip(categories: dict, total_logs: int) -> str:
    """Generate actionable next-step tip"""
    tips = [
        "Keep tracking to spot more patterns.",
        "Try setting a weekly spending goal.",
        "Review your top categories for savings opportunities.",
        "Consider tracking smaller daily expenses too."
    ]
    
    # Simple tip selection based on data
    if total_logs < 5:
        return "Log more expenses to unlock deeper insights."
    elif len(categories) == 1:
        return "Try categorizing expenses for better analysis."
    else:
        import random
        return random.choice(tips)


def _emit_telemetry_event(user_id: str):
    """Emit telemetry event for report request"""
    try:
        import time
        from utils.structured import log_structured_event
        
        # Determine window days (same logic as main function)
        window_days = _get_time_window(user_id)
        
        event_data = {
            "user_id": user_id,
            "source": "user_command", 
            "window_days": window_days,
            "timestamp": time.time()
        }
        
        log_structured_event("report_requested", event_data, user_id)
        logger.info(f"Telemetry: report_requested for user {user_id[:8]}")
        
    except Exception as e:
        # Telemetry failures should not break the main flow
        logger.debug(f"Telemetry emission failed: {e}")