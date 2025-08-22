"""Database operations and connection utilities"""
import logging
from datetime import datetime, date
from sqlalchemy.exc import SQLAlchemyError
from utils.identity import psid_hash

logger = logging.getLogger(__name__)

def get_or_create_user(user_identifier, platform, db_session=None):
    """Get existing user or create new one with hashed ID"""
    from models import User
    from flask import current_app
    
    if db_session is None:
        from app import db
        db_session = db
    
    try:
        user_hash = user_identifier  # Already hashed
        
        user = User.query.filter_by(user_id_hash=user_hash).first()
        
        if not user:
            user = User(
                user_id_hash=user_hash,
                platform=platform,
                total_expenses=0,
                expense_count=0
            )
            db_session.session.add(user)
            db_session.session.commit()
            logger.info(f"Created new user for platform {platform}")
        
        return user
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_or_create_user: {str(e)}")
        db_session.session.rollback()
        return None

def save_expense(user_identifier, description, amount, category, platform, original_message, unique_id, db_session=None):
    """Save expense to database and update monthly summaries"""
    from models import Expense, User, MonthlySummary
    from utils.tracer import trace_event
    from utils.identity import psid_hash
    
    if db_session is None:
        from app import db
        db_session = db
    
    try:
        # User identifier is already hashed when passed from production_router
        user_hash = user_identifier
        
        # Strict validation in debug mode
        import os
        if os.environ.get('STRICT_IDS', 'false').lower() == 'true':
            from utils.crypto import is_sha256_hex
            assert is_sha256_hex(user_hash), f"Invalid user_id for DB write: {user_hash}"
        
        # Trace the write operation
        trace_event("record_expense", user_id=user_hash, amount=amount, category=category, path="write")
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
            monthly_summary = MonthlySummary(
                user_id_hash=user_hash,
                month=current_month,
                total_amount=amount,
                expense_count=1,
                categories={category: float(amount)}
            )
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
        
        return {
            'success': True,
            'monthly_total': float(monthly_summary.total_amount),
            'expense_count': monthly_summary.expense_count
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

def save_expense_idempotent(user_identifier, description, amount, category, currency, platform, original_message, unique_id, db_session=None):
    """
    Save expense with idempotency protection using Facebook message ID.
    Returns: {'duplicate': bool, 'timestamp': str, 'success': bool}
    """
    from models import Expense, User, MonthlySummary
    from utils.tracer import trace_event
    from datetime import datetime, date
    import hashlib
    
    if db_session is None:
        from app import db
        db_session = db
    
    try:
        user_hash = user_identifier  # Already hashed
        
        # Compute idempotency key: SHA256(psid_hash + mid)
        idempotency_key = hashlib.sha256(f"{user_hash}{unique_id}".encode()).hexdigest()
        
        # Check for existing expense with same idempotency key
        existing_expense = db_session.session.query(Expense).filter_by(
            user_id=user_hash,
            mid=unique_id  # Use mid field for Facebook message ID
        ).first()
        
        if existing_expense:
            # Return duplicate info with timestamp
            timestamp = existing_expense.created_at.strftime("%H:%M") if existing_expense.created_at else "earlier"
            logger.info(f"Duplicate expense detected: user={user_hash[:8]}... mid={unique_id}")
            return {
                'duplicate': True,
                'timestamp': timestamp,
                'success': False,
                'expense_id': existing_expense.id
            }
        
        # No duplicate found - proceed with normal save
        trace_event("record_expense_idempotent", user_id=user_hash, amount=amount, category=category, mid=unique_id)
        
        current_date = date.today()
        current_time = datetime.now().time()
        current_month = current_date.strftime('%Y-%m')
        
        # Create expense record with idempotency protection
        expense = Expense(
            user_id=user_hash,
            description=description,
            amount=amount,
            category=category,
            currency=currency,
            date=current_date,
            time=current_time,
            month=current_month,
            unique_id=idempotency_key,  # Store computed idempotency key
            mid=unique_id,  # Store Facebook message ID for duplicate detection
            platform=platform,
            original_message=original_message
        )
        
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
            monthly_summary = MonthlySummary(
                user_id_hash=user_hash,
                month=current_month,
                total_amount=amount,
                expense_count=1,
                categories={category: float(amount)}
            )
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
        
        logger.info(f"Expense saved with idempotency: user={user_hash[:8]}... mid={unique_id} amount={amount}")
        return {
            'duplicate': False,
            'success': True,
            'expense_id': expense.id,
            'monthly_total': float(monthly_summary.total_amount),
            'expense_count': monthly_summary.expense_count
        }
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in save_expense_idempotent: {str(e)}")
        db_session.session.rollback()
        return {'duplicate': False, 'success': False, 'error': str(e)}
