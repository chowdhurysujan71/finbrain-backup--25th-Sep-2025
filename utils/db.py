"""Database operations and connection utilities"""
import logging
from app import db
from models import Expense, User, MonthlySummary, RateLimit
from datetime import datetime, date
from sqlalchemy.exc import SQLAlchemyError
from utils.security import hash_user_id

logger = logging.getLogger(__name__)

def get_or_create_user(user_identifier, platform):
    """Get existing user or create new one with hashed ID"""
    try:
        user_hash = hash_user_id(user_identifier)
        
        user = User.query.filter_by(user_id_hash=user_hash).first()
        
        if not user:
            user = User(
                user_id_hash=user_hash,
                platform=platform,
                total_expenses=0,
                expense_count=0
            )
            db.session.add(user)
            db.session.commit()
            logger.info(f"Created new user for platform {platform}")
        
        return user
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_or_create_user: {str(e)}")
        db.session.rollback()
        return None

def save_expense(user_identifier, description, amount, category, platform, original_message, unique_id):
    """Save expense to database and update monthly summaries"""
    try:
        user_hash = hash_user_id(user_identifier)
        current_date = date.today()
        current_time = datetime.now().time()
        current_month = current_date.strftime('%Y-%m')
        
        # Create expense record
        expense = Expense(
            user_id=user_hash,
            description=description,
            amount=amount,
            category=category,
            date=current_date,
            time=current_time,
            month=current_month,
            unique_id=unique_id,
            platform=platform,
            original_message=original_message
        )
        
        db.session.add(expense)
        
        # Update user totals
        user = get_or_create_user(user_identifier, platform)
        if user:
            user.total_expenses = float(user.total_expenses) + float(amount)
            user.expense_count += 1
            user.last_interaction = datetime.utcnow()
        
        # Update monthly summary
        monthly_summary = MonthlySummary.query.filter_by(
            user_id_hash=user_hash,
            month=current_month
        ).first()
        
        if not monthly_summary:
            monthly_summary = MonthlySummary(
                user_id_hash=user_hash,
                month=current_month,
                total_amount=amount,
                expense_count=1,
                categories={category: float(amount)}
            )
            db.session.add(monthly_summary)
        else:
            monthly_summary.total_amount = float(monthly_summary.total_amount) + float(amount)
            monthly_summary.expense_count += 1
            
            # Update category breakdown
            categories = monthly_summary.categories or {}
            categories[category] = categories.get(category, 0) + float(amount)
            monthly_summary.categories = categories
            monthly_summary.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return {
            'success': True,
            'monthly_total': float(monthly_summary.total_amount),
            'expense_count': monthly_summary.expense_count
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error saving expense: {str(e)}")
        db.session.rollback()
        return {'success': False, 'error': str(e)}

def get_monthly_summary(user_identifier, month=None):
    """Get monthly summary for a user"""
    try:
        user_hash = hash_user_id(user_identifier)
        
        if not month:
            month = date.today().strftime('%Y-%m')
        
        summary = MonthlySummary.query.filter_by(
            user_id_hash=user_hash,
            month=month
        ).first()
        
        if summary:
            return {
                'total_amount': float(summary.total_amount),
                'expense_count': summary.expense_count,
                'categories': summary.categories or {},
                'month': summary.month
            }
        
        return {
            'total_amount': 0,
            'expense_count': 0,
            'categories': {},
            'month': month
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting monthly summary: {str(e)}")
        return {
            'total_amount': 0,
            'expense_count': 0,
            'categories': {},
            'month': month or date.today().strftime('%Y-%m')
        }

def get_user_expenses(user_identifier, limit=10):
    """Get recent expenses for a user"""
    try:
        user_hash = hash_user_id(user_identifier)
        
        expenses = Expense.query.filter_by(user_id=user_hash)\
                               .order_by(Expense.created_at.desc())\
                               .limit(limit)\
                               .all()
        
        return [{
            'description': expense.description,
            'amount': float(expense.amount),
            'category': expense.category,
            'date': expense.date.isoformat(),
            'time': expense.time.isoformat()
        } for expense in expenses]
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting user expenses: {str(e)}")
        return []
