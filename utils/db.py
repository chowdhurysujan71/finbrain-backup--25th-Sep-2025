"""Database operations and connection utilities"""
import logging
from datetime import date, datetime

from sqlalchemy.exc import SQLAlchemyError

from utils.identity import psid_hash

logger = logging.getLogger(__name__)


def get_or_create_user(user_identifier, platform, db_session=None):
    """Get or create user by identifier"""
    from models import User
    
    if db_session is None:
        from db_base import db
        db_session = db

    try:
        user_hash = user_identifier  # Already hashed
        
        # Use no_autoflush to prevent triggering flush of pending expense
        with db_session.session.no_autoflush:
            user = db_session.session.query(User).filter_by(user_id_hash=user_hash).first()
        
        if not user:
            user = User()
            user.user_id_hash = user_hash
            user.platform = platform
            user.total_expenses = 0
            user.expense_count = 0
            db_session.session.add(user)
            logger.info(f"Created new user for platform {platform}")
        
        return user
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_or_create_user: {str(e)}")
        # Re-raise to let caller handle transaction rollback
        raise

# REMOVED: save_expense() - DEPRECATED ghost code eliminated 2025-09-20
# Use backend_assistant.add_expense() instead (canonical single writer)

def get_monthly_summary(user_identifier, month=None):
    """Get monthly summary for a user"""
    from models import MonthlySummary
    
    try:
        user_hash = psid_hash(user_identifier) if len(user_identifier) < 64 else user_identifier
        
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
            'month': month or date.today().strftime('%Y-%m')
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
    from models import Expense
    
    try:
        user_hash = psid_hash(user_identifier) if len(user_identifier) < 64 else user_identifier
        
        # Security pattern: EXECUTE recent_expenses - using prepared statement via ORM
        expenses = Expense.query.filter_by(user_id_hash=user_hash)\
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

# REMOVED: upsert_expense_idempotent() - DEPRECATED ghost code eliminated 2025-09-20
# Use backend_assistant.add_expense() instead (canonical single writer)

def ensure_idempotency_index():
    """
    Ensure the unique index for idempotency exists.
    Safe to call multiple times.
    """
    try:
        from db_base import db
        
        # Create unique index if it doesn't exist
        index_sql = """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_expenses_psid_mid 
        ON expenses(user_id, mid) 
        WHERE mid IS NOT NULL AND mid != '';
        """
        
        from sqlalchemy import text
        db.session.execute(text(index_sql))
        db.session.commit()
        
        logger.info("Idempotency index ensured: ux_expenses_psid_mid")
        return True
        
    except Exception as e:
        logger.error(f"Failed to ensure idempotency index: {e}")
        return False

# REMOVED: save_expense_idempotent() - DEPRECATED ghost code eliminated 2025-09-20
# Use backend_assistant.add_expense() instead (canonical single writer)