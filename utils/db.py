"""Database operations and connection utilities"""
import logging
from datetime import date, datetime

from sqlalchemy.exc import SQLAlchemyError

from utils.identity import psid_hash

logger = logging.getLogger(__name__)

# REMOVED: create_expense() - DEPRECATED ghost code eliminated 2025-09-20
# Use backend_assistant.add_expense() instead (canonical single writer)

def get_or_create_user(user_identifier, platform, db_session=None):
    """Get existing user or create new one with hashed ID"""
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
        current_time = datetime.now().time()
        current_month = current_date.strftime('%Y-%m')
        
        # Create expense record
        expense = Expense()
        expense.user_id = user_hash
        expense.user_id_hash = user_hash  # Ensure both fields are set for data integrity
        expense.description = description
        expense.amount = amount
        expense.category = category
        expense.date = current_date
        expense.time = current_time
        expense.month = current_month
        expense.unique_id = unique_id
        expense.platform = platform
        expense.original_message = original_message
        expense.mid = mid
        
        db_session.session.add(expense)
        
        # Update user totals
        user = get_or_create_user(user_hash, platform, db_session)
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
            monthly_summary = MonthlySummary()
            monthly_summary.user_id_hash = user_hash
            monthly_summary.month = current_month
            monthly_summary.total_amount = amount
            monthly_summary.expense_count = 1
            monthly_summary.categories = {category: float(amount)}
            db_session.session.add(monthly_summary)
        else:
            monthly_summary.total_amount = float(monthly_summary.total_amount) + float(amount)
            monthly_summary.expense_count += 1
            
            # Update category breakdown
            categories = monthly_summary.categories or {}
            categories[category] = categories.get(category, 0) + float(amount)
            monthly_summary.categories = categories
            monthly_summary.updated_at = datetime.utcnow()
        
        db_session.session.commit()
        
        # PHASE F GROWTH TELEMETRY: Track expense_logged event (fail-safe)
        try:
            # Determine source based on platform
            source_mapping = {
                'messenger': 'messenger',
                'form': 'form',
                'web': 'form',
                'pwa': 'form'
            }
            source = source_mapping.get(platform, 'form')
            
            TelemetryTracker.track_expense_logged(
                user_id_hash=user_hash,
                amount=float(amount),
                category=category,
                source=source
            )
        except Exception as e:
            # Fail-safe: telemetry errors never break expense logging
            logger.debug(f"Growth telemetry tracking failed: {e}")
        
        # ANALYTICS: Track successful expense logging (100% additive, fail-safe)
        try:
            from utils.lightweight_analytics import track_expense_success
            track_expense_success(user_hash, float(amount), category)
        except Exception as e:
            # Fail-safe: analytics errors never break expense logging
            logger.debug(f"Expense analytics tracking failed: {e}")
        
        # BLOCK 4 GROWTH METRICS: Analytics and Milestones (fail-safe)
        milestone_message = None
        try:
            from utils.analytics_engine import track_d1_activation, track_d3_completion
            from utils.milestone_engine import (
                check_milestone_nudges,
                update_user_streak,
            )
            from utils.timezone_helpers import local_date_from_datetime
            
            # Get expense local date for streak calculations
            expense_datetime = datetime.combine(current_date, current_time)
            expense_local_date = local_date_from_datetime(expense_datetime)
            
            # Track D1/D3 analytics (silent data collection) - with null check
            if user:
                track_d1_activation(user, expense_datetime)
                track_d3_completion(user)
                
                # Update user streak and check milestones (user-visible nudges)
                if expense_local_date:
                    update_user_streak(user, expense_local_date)
                    milestone_message = check_milestone_nudges(user)
                
        except Exception as e:
            # Fail-safe: growth metrics errors never break expense logging
            logger.debug(f"Growth metrics tracking failed: {e}")
        
        return {
            'success': True,
            'monthly_total': float(monthly_summary.total_amount),
            'expense_count': monthly_summary.expense_count,
            'milestone_message': milestone_message  # Include milestone nudge if triggered
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error saving expense: {str(e)}")
        db_session.session.rollback()
        return {'success': False, 'error': str(e)}

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
    from models import Expense
    
    try:
        user_hash = psid_hash(user_identifier) if len(user_identifier) < 64 else user_identifier
        
        # Security pattern: EXECUTE recent_expenses - using prepared statement via ORM
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
