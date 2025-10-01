"""
Atomic Event Hooks - Single Source of Truth for UI Updates
Foundation layer for deterministic, testable expense processing cascade
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

from db_base import db
from models import Expense, Goal

logger = logging.getLogger(__name__)

# Asia/Dhaka timezone for all date/time operations
DHAKA_TZ = ZoneInfo("Asia/Dhaka")


def on_expense_committed(expense_id: int, user_id_hash: str) -> Dict[str, Any]:
    """
    Atomic event hook triggered when an expense is committed (added/edited/undeleted).
    
    Returns all UI components that need to update in a single deterministic call.
    This is the single source of truth for post-expense UI state.
    
    Args:
        expense_id: The committed expense ID
        user_id_hash: User identifier for security and scoping
        
    Returns:
        {
            'success': bool,
            'expense_id': int,
            'confirmation': {...},      # Expense confirmation details
            'chart_update': {...},      # Category breakdown data
            'progress_ring': {...},     # Goal progress state
            'banner': {...} or None,    # Smart banner if eligible
            'celebration': {...} or None, # Milestone celebration if any
            'timestamp': str,           # Event timestamp (Asia/Dhaka)
            'error': str or None        # Error message if failed
        }
    """
    try:
        # Fetch and validate expense
        expense = Expense.query.filter(
            Expense.id == expense_id,
            Expense.user_id_hash == user_id_hash,
            Expense.is_deleted.is_(False)  # type: ignore
        ).first()
        
        if not expense:
            logger.warning(f"Expense {expense_id} not found or deleted for user {user_id_hash[:8]}...")
            return {
                'success': False,
                'expense_id': expense_id,
                'error': 'Expense not found or has been deleted',
                'timestamp': datetime.now(DHAKA_TZ).isoformat()
            }
        
        # Calculate all UI components atomically
        confirmation = _build_confirmation(expense)
        chart_update = _build_chart_update(user_id_hash, expense.date)
        progress_ring = _build_progress_ring(user_id_hash, expense.date)
        banner = _evaluate_banner(user_id_hash, expense)
        celebration = _check_celebration(user_id_hash, expense)
        
        return {
            'success': True,
            'expense_id': expense_id,
            'confirmation': confirmation,
            'chart_update': chart_update,
            'progress_ring': progress_ring,
            'banner': banner,
            'celebration': celebration,
            'timestamp': datetime.now(DHAKA_TZ).isoformat(),
            'error': None
        }
        
    except Exception as e:
        logger.error(f"on_expense_committed failed for expense {expense_id}: {e}", exc_info=True)
        return {
            'success': False,
            'expense_id': expense_id,
            'error': f'Failed to process expense update: {str(e)}',
            'timestamp': datetime.now(DHAKA_TZ).isoformat()
        }


def _build_confirmation(expense: Expense) -> Dict[str, Any]:
    """Build expense confirmation component"""
    amount = float(expense.amount_minor) / 100
    return {
        'amount': amount,
        'currency': expense.currency,
        'category': expense.category,
        'description': expense.description or '',
        'date': expense.date.isoformat(),
        'message': f"Added {expense.currency}{amount:.0f} {expense.category}"
    }


def _build_chart_update(user_id_hash: str, expense_date: date) -> Dict[str, Any]:
    """Build category breakdown chart data for the expense's date"""
    try:
        # Get all expenses for the same day
        day_expenses = Expense.query.filter(
            Expense.user_id_hash == user_id_hash,
            Expense.date == expense_date,
            Expense.is_deleted.is_(False)  # type: ignore
        ).all()
        
        # Calculate category breakdown
        category_totals = {}
        total_amount = 0
        
        for exp in day_expenses:
            category = exp.category or 'Uncategorized'
            amount = float(exp.amount_minor) / 100
            category_totals[category] = category_totals.get(category, 0) + amount
            total_amount += amount
        
        # Build chart data with percentages
        categories = []
        for category, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            percentage = (amount / total_amount * 100) if total_amount > 0 else 0
            categories.append({
                'category': category,
                'amount': round(amount, 2),
                'percentage': round(percentage, 1)
            })
        
        return {
            'date': expense_date.isoformat(),
            'total': round(total_amount, 2),
            'categories': categories,
            'count': len(day_expenses)
        }
        
    except Exception as e:
        logger.error(f"Chart update failed: {e}")
        return {'error': str(e), 'categories': []}


def _build_progress_ring(user_id_hash: str, expense_date: date) -> Dict[str, Any]:
    """Build goal progress ring component"""
    try:
        # Get active daily spending goal
        active_goals = Goal.get_active_for_user(user_id_hash, 'daily_spend_under')
        
        if not active_goals:
            return {
                'has_goal': False,
                'message': 'No active goal set'
            }
        
        goal = active_goals[0]
        goal_amount = float(goal.amount)
        
        # Calculate today's spending
        today_total = db.session.query(
            db.func.sum(Expense.amount_minor)
        ).filter(
            Expense.user_id_hash == user_id_hash,
            Expense.date == expense_date,
            Expense.is_deleted.is_(False)  # type: ignore
        ).scalar() or 0
        
        today_spent = float(today_total) / 100
        percentage = (today_spent / goal_amount * 100) if goal_amount > 0 else 0
        remaining = goal_amount - today_spent
        
        # Determine status
        if percentage >= 100:
            status = 'over'
            message = f"৳{today_spent:.0f} spent (৳{abs(remaining):.0f} over goal)"
        elif percentage >= 80:
            status = 'warning'
            message = f"৳{today_spent:.0f} spent (৳{remaining:.0f} left)"
        else:
            status = 'good'
            message = f"৳{today_spent:.0f} spent (৳{remaining:.0f} left)"
        
        return {
            'has_goal': True,
            'goal_amount': goal_amount,
            'spent': round(today_spent, 2),
            'remaining': round(remaining, 2),
            'percentage': round(percentage, 1),
            'status': status,
            'message': message
        }
        
    except Exception as e:
        logger.error(f"Progress ring failed: {e}")
        return {
            'has_goal': False,
            'error': str(e)
        }


def _evaluate_banner(user_id_hash: str, expense: Expense) -> Optional[Dict[str, Any]]:
    """Evaluate if a smart banner should be shown"""
    try:
        from utils.smart_banners import SmartBannerService
        
        # Initialize banner service and check for goal-aware banners
        banner_service = SmartBannerService()
        banners = banner_service.get_goal_aware_banners(user_id_hash, limit=1)
        
        # Return first banner if available
        if banners and len(banners) > 0:
            return banners[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Banner evaluation failed: {e}")
        return None


def _check_celebration(user_id_hash: str, expense: Expense) -> Optional[Dict[str, Any]]:
    """Check if expense triggers a milestone celebration"""
    try:
        from sqlalchemy import func, distinct
        
        # Check for 7-day streak: expenses on 7 consecutive days
        streak_days = db.session.query(
            distinct(Expense.date)
        ).filter(
            Expense.user_id_hash == user_id_hash,
            Expense.is_deleted.is_(False)  # type: ignore
        ).order_by(Expense.date.desc()).limit(7).all()
        
        if len(streak_days) == 7:
            # Check if dates are consecutive
            dates = sorted([d[0] for d in streak_days])
            is_consecutive = all(
                (dates[i+1] - dates[i]).days == 1 
                for i in range(len(dates)-1)
            )
            
            if is_consecutive:
                return {
                    'type': '7_day_streak',
                    'title': '🔥 7-Day Streak!',
                    'message': 'Amazing! You\'ve tracked expenses for 7 days straight. Building great financial habits!',
                    'icon': '🔥',
                    'style': 'success'
                }
        
        # Check for 100th expense milestone
        total_expenses = Expense.query.filter(
            Expense.user_id_hash == user_id_hash,
            Expense.is_deleted.is_(False)  # type: ignore
        ).count()
        
        if total_expenses == 100:
            return {
                'type': '100th_expense',
                'title': '🎉 100 Expenses Tracked!',
                'message': 'Congratulations! You\'ve logged 100 expenses. Your financial awareness is on fire!',
                'icon': '🎉',
                'style': 'success'
            }
        
        # Check for first expense of the month
        month_start = expense.date.replace(day=1)
        month_expenses = Expense.query.filter(
            Expense.user_id_hash == user_id_hash,
            Expense.date >= month_start,
            Expense.date < expense.date + timedelta(days=1),
            Expense.is_deleted.is_(False)  # type: ignore
        ).count()
        
        if month_expenses == 1:
            month_name = expense.date.strftime('%B')
            return {
                'type': 'first_of_month',
                'title': f'📅 First Expense of {month_name}!',
                'message': f'Starting {month_name} strong! Keep tracking to build a complete picture of your spending.',
                'icon': '📅',
                'style': 'info'
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Celebration check failed: {e}")
        return None
