"""Automated report generation for daily and weekly summaries"""
import logging
from datetime import datetime, date, timedelta
from utils.db import get_monthly_summary, get_user_expenses

from utils.facebook_handler import send_facebook_report
from models import User, Expense
from app import db

logger = logging.getLogger(__name__)

def generate_daily_report(user_identifier, platform):
    """Generate daily expense report for user"""
    try:
        from utils.security import hash_user_id
        
        user_hash = ensure_hashed(user_identifier)
        today = date.today()
        
        # Get today's expenses
        today_expenses = Expense.query.filter(
            Expense.user_id_hash == user_hash,
            Expense.date == today
        ).all()
        
        if not today_expenses:
            return "📊 Daily Report: No expenses logged today."
        
        total_amount = sum(float(expense.amount) for expense in today_expenses)
        expense_count = len(today_expenses)
        
        # Calculate category breakdown
        categories = {}
        for expense in today_expenses:
            categories[expense.category] = categories.get(expense.category, 0) + float(expense.amount)
        
        # Format report
        report = f"📊 Daily Report - {today.strftime('%Y-%m-%d')}\n\n"
        report += f"💰 Total Spent: ৳{total_amount:.2f}\n"
        report += f"📝 Transactions: {expense_count}\n\n"
        
        if categories:
            report += "📋 Categories:\n"
            for category, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                from utils.expense import get_category_emoji
                emoji = get_category_emoji(category)
                percentage = (amount / total_amount * 100) if total_amount > 0 else 0
                report += f"{emoji} {category}: ৳{amount:.2f} ({percentage:.1f}%)\n"
        
        # Get current month total
        current_month = today.strftime('%Y-%m')
        monthly_summary = get_monthly_summary(user_identifier, current_month)
        
        report += f"\n📈 Month Total: ৳{monthly_summary['total_amount']:.2f}"
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating daily report: {str(e)}")
        return "Error generating daily report."

def generate_weekly_report(user_identifier, platform):
    """Generate weekly expense report for user"""
    try:
        from utils.security import hash_user_id
        
        user_hash = ensure_hashed(user_identifier)
        today = date.today()
        week_start = today - timedelta(days=6)  # Last 7 days
        
        # Get week's expenses
        week_expenses = Expense.query.filter(
            Expense.user_id_hash == user_hash,
            Expense.date >= week_start,
            Expense.date <= today
        ).all()
        
        if not week_expenses:
            return "📊 Weekly Report: No expenses logged this week."
        
        total_amount = sum(float(expense.amount) for expense in week_expenses)
        expense_count = len(week_expenses)
        daily_average = total_amount / 7
        
        # Calculate category breakdown
        categories = {}
        daily_totals = {}
        
        for expense in week_expenses:
            # Categories
            categories[expense.category] = categories.get(expense.category, 0) + float(expense.amount)
            
            # Daily totals
            expense_date = expense.date.strftime('%Y-%m-%d')
            daily_totals[expense_date] = daily_totals.get(expense_date, 0) + float(expense.amount)
        
        # Format report
        report = f"📊 Weekly Report - {week_start.strftime('%m/%d')} to {today.strftime('%m/%d')}\n\n"
        report += f"💰 Total Spent: ৳{total_amount:.2f}\n"
        report += f"📝 Transactions: {expense_count}\n"
        report += f"📈 Daily Average: ৳{daily_average:.2f}\n\n"
        
        # Top categories
        if categories:
            report += "🏆 Top Categories:\n"
            sorted_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
            for category, amount in sorted_categories:
                from utils.expense import get_category_emoji
                emoji = get_category_emoji(category)
                percentage = (amount / total_amount * 100) if total_amount > 0 else 0
                report += f"{emoji} {category}: ৳{amount:.2f} ({percentage:.1f}%)\n"
        
        # Spending trend
        if len(daily_totals) > 1:
            recent_days = sorted(daily_totals.items())[-3:]
            if len(recent_days) >= 2:
                trend = recent_days[-1][1] - recent_days[-2][1]
                if trend > 0:
                    report += f"\n📈 Trend: +৳{trend:.2f} vs yesterday"
                elif trend < 0:
                    report += f"\n📉 Trend: ৳{trend:.2f} vs yesterday"
                else:
                    report += f"\n➡️ Trend: Same as yesterday"
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating weekly report: {str(e)}")
        return "Error generating weekly report."

def send_daily_reports():
    """MVP: No scheduled outbound messages (24-hour policy compliance)"""
    logger.info("Daily reports disabled for MVP - 24-hour policy compliance")
    return

def send_weekly_reports():
    """MVP: No scheduled outbound messages (24-hour policy compliance)"""
    logger.info("Weekly reports disabled for MVP - 24-hour policy compliance")
    return
