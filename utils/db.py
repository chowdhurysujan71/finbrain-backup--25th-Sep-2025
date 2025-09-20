"""Database operations and connection utilities"""
import logging
from datetime import datetime, date
from typing import Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from utils.identity import psid_hash

logger = logging.getLogger(__name__)

def create_expense(user_id, amount, currency, category, occurred_at, source_message_id, correlation_id, notes, idempotency_key=None):
    """
    Unified expense creation function - single source of truth for expense writes
    Both Chat and Quick Add must call this function synchronously
    
    Args:
        user_id: User identifier (already hashed)
        amount: Expense amount (float)
        currency: Currency symbol (e.g., '৳', '$')
        category: Expense category (string)
        occurred_at: When expense occurred (datetime)
        source_message_id: ID of source message (for audit trail)
        correlation_id: UUID for idempotency
        notes: Additional notes/description
        
    Returns:
        dict: {expense_id, correlation_id, occurred_at, category, amount, currency}
    """
    from models import Expense, User, MonthlySummary
    from utils.tracer import trace_event
    from utils.telemetry import TelemetryTracker
    from db_base import db
    import uuid
    from decimal import Decimal
    
    try:
        # Validate inputs
        if not user_id or not amount or not category:
            raise ValueError("user_id, amount, and category are required")
            
        # Validate amount
        MAX_AMOUNT = 99999999.99
        MIN_AMOUNT = 0.01
        amount_float = float(amount)
        if amount_float > MAX_AMOUNT or amount_float < MIN_AMOUNT:
            raise ValueError(f"Amount must be between ৳{MIN_AMOUNT} and ৳{MAX_AMOUNT:,.2f}")
        
        # Generate correlation_id if not provided
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            
        # Trace the write operation
        trace_event("record_expense", user_id=user_id, amount=amount_float, category=category, path="write")
        
        # Create expense record with UPSERT for idempotency
        current_month = occurred_at.strftime('%Y-%m')
        
        expense = Expense()
        expense.user_id = user_id
        expense.user_id_hash = user_id  # Ensure both fields are set
        expense.description = notes or f"{category} expense"
        expense.amount = Decimal(str(amount_float))
        # Use Decimal arithmetic to avoid floating-point precision errors
        expense.amount_minor = int(Decimal(str(amount_float)).quantize(Decimal('0.01')) * 100)
        # Apply category normalization guard if enabled
        from utils.pca_flags import pca_flags
        if pca_flags.should_normalize_categories():
            from utils.category_guard import normalize_category_for_save
            expense.category = normalize_category_for_save(category)
        else:
            expense.category = category.lower()  # Existing behavior
        expense.currency = currency or '৳'
        expense.date = occurred_at.date()
        expense.time = occurred_at.time()
        expense.month = current_month
        expense.platform = "pwa"  # Unified platform
        expense.original_message = notes or f"Expense: {amount_float} {currency} for {category}"
        expense.correlation_id = correlation_id
        expense.unique_id = str(uuid.uuid4())
        expense.mid = source_message_id
        # Set idempotency_key (use passed key or generate fallback)
        expense.idempotency_key = idempotency_key or f"api:{correlation_id}"
        
        # UPSERT: Check for existing expense by idempotency_key before inserting
        existing_expense = Expense.query.filter_by(idempotency_key=expense.idempotency_key).first()
        if existing_expense:
            logger.info(f"Idempotency: returning existing expense for key {expense.idempotency_key[:20]}***")
            return {
                'expense_id': existing_expense.id,
                'correlation_id': existing_expense.correlation_id,
                'occurred_at': existing_expense.created_at.isoformat(),
                'category': existing_expense.category,
                'amount': float(existing_expense.amount),
                'currency': existing_expense.currency,
                'description': existing_expense.description,
                'status': 'idempotent_replay'
            }
        
        # Atomic transaction
        db.session.add(expense)
        
        # Update user totals (concurrent-safe UPSERT) - prevent autoflush
        from sqlalchemy import text as sql_text
        now_ts = datetime.utcnow()
        with db.session.no_autoflush:
            db.session.execute(sql_text("""
                INSERT INTO users (user_id_hash, platform, total_expenses, expense_count, last_interaction, last_user_message_at)
                VALUES (:user_hash, 'pwa', :amount, 1, :now_ts, :now_ts)
                ON CONFLICT (user_id_hash) DO UPDATE SET
                    total_expenses = COALESCE(users.total_expenses, 0) + :amount,
                    expense_count = COALESCE(users.expense_count, 0) + 1,
                    last_interaction = :now_ts,
                    last_user_message_at = :now_ts
            """), {
                'user_hash': user_id,
                'amount': amount_float,
                'now_ts': now_ts
            })
        
        # Update monthly summary - prevent autoflush during query
        with db.session.no_autoflush:
            monthly_summary = MonthlySummary.query.filter_by(
                user_id_hash=user_id,
                month=current_month
            ).first()
            
            if not monthly_summary:
                monthly_summary = MonthlySummary()
                monthly_summary.user_id_hash = user_id
                monthly_summary.month = current_month
                monthly_summary.total_amount = amount_float
                monthly_summary.expense_count = 1
                monthly_summary.categories = {expense.category: amount_float}
                db.session.add(monthly_summary)
            else:
                monthly_summary.total_amount = float(monthly_summary.total_amount) + amount_float
                monthly_summary.expense_count += 1
                categories = monthly_summary.categories or {}
                categories[expense.category] = categories.get(expense.category, 0) + amount_float
                monthly_summary.categories = categories
                monthly_summary.updated_at = datetime.utcnow()
        
        # Single atomic commit
        db.session.commit()
        
        # Log telemetry
        try:
            TelemetryTracker.track_expense_logged(user_id, amount_float, expense.category)
        except Exception as e:
            logger.warning(f"Telemetry logging failed: {e}")
        
        return {
            'expense_id': expense.id,
            'correlation_id': correlation_id,
            'occurred_at': occurred_at.isoformat(),
            'category': expense.category,
            'amount': amount_float,
            'currency': currency or '৳',
            'description': expense.description
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"create_expense failed: {e}")
        raise

def get_or_create_user(user_identifier, platform, db_session=None):
    """Get existing user or create new one with hashed ID"""
    from models import User
    from flask import current_app
    
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

def save_expense(user_identifier, description, amount, category, platform, original_message, unique_id, mid=None, db_session=None):
    """Save expense to database and update monthly summaries"""
    from models import Expense, User, MonthlySummary
    from utils.tracer import trace_event
    from utils.identity import psid_hash
    from utils.telemetry import TelemetryTracker
    
    if db_session is None:
        from db_base import db
        db_session = db
    
    try:
        # User identifier is already hashed when passed from production_router
        user_hash = user_identifier
        
        # Validate amount to prevent database overflow
        # Database field is Numeric(10, 2) so max is 99,999,999.99
        MAX_AMOUNT = 99999999.99
        MIN_AMOUNT = 0.01
        
        amount_float = float(amount)
        if amount_float > MAX_AMOUNT:
            raise ValueError(f"Amount {amount_float} exceeds maximum allowed value of ৳{MAX_AMOUNT:,.2f}")
        if amount_float < MIN_AMOUNT:
            raise ValueError(f"Amount {amount_float} below minimum allowed value of ৳{MIN_AMOUNT}")
        
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
            from utils.milestone_engine import update_user_streak, check_milestone_nudges
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

def upsert_expense_idempotent(psid_hash: str, mid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced idempotent expense saving with comprehensive payload support.
    
    Args:
        psid_hash: User PSID hash (already hashed)
        mid: Facebook message ID for idempotency
        payload: Expense data with keys: amount, currency, category, merchant, description, etc.
        
    Returns:
        Dict with keys: duplicate, success, timestamp, expense_id, etc.
    """
    from models import Expense, User, MonthlySummary
    from utils.tracer import trace_event
    from datetime import datetime, date
    from decimal import Decimal
    import hashlib
    
    from db_base import db
    
    try:
        # Create unique constraint key
        constraint_key = f"{psid_hash}:{mid}"
        
        # Check for existing expense with same (psid_hash, mid)
        existing_expense = db.session.query(Expense).filter_by(
            user_id=psid_hash,
            mid=mid
        ).first()
        
        if existing_expense:
            # Return duplicate info
            timestamp = existing_expense.created_at.strftime("%H:%M") if existing_expense.created_at else "earlier"
            logger.info(f"Duplicate detected: user={psid_hash[:8]}... mid={mid}")
            
            return {
                'duplicate': True,
                'idempotent': True,
                'timestamp': timestamp,
                'success': False,
                'expense_id': existing_expense.id,
                'amount': float(existing_expense.amount),
                'currency': existing_expense.currency or 'BDT'
            }
        
        # Extract data from payload
        amount = Decimal(str(payload['amount']))
        currency = payload.get('currency', 'BDT')
        from utils.categories import normalize_category
        category = normalize_category(payload.get('category'))
        merchant = payload.get('merchant')
        description = payload.get('description', f"{category} expense")
        ts_client = payload.get('ts_client')  # Client-side timestamp
        
        # Use client timestamp or current time
        expense_datetime = ts_client if ts_client else datetime.utcnow()
        current_date = expense_datetime.date()
        current_time = expense_datetime.time()
        current_month = current_date.strftime('%Y-%m')
        
        # Generate unique_id for this expense
        unique_id = hashlib.sha256(f"{psid_hash}{mid}{amount}{category}".encode()).hexdigest()
        
        # Trace the operation
        trace_event("upsert_expense_idempotent", 
                   user_id=psid_hash, amount=amount, category=category, 
                   mid=mid, merchant=merchant)
        
        # Create expense record
        expense = Expense()
        expense.user_id = psid_hash
        expense.description = description
        expense.amount = amount
        expense.category = category
        expense.currency = currency
        expense.date = current_date
        expense.time = current_time
        expense.month = current_month
        expense.unique_id = unique_id
        expense.mid = mid  # Store Facebook message ID
        expense.platform = 'facebook'
        expense.original_message = payload.get('original_message', description)
        
        db.session.add(expense)
        
        # Update user totals
        user = get_or_create_user(psid_hash, 'facebook', db)
        if user:
            user.total_expenses = float(user.total_expenses or 0) + float(amount)
            user.expense_count = (user.expense_count or 0) + 1
            user.last_interaction = datetime.utcnow()
        
        # Update monthly summary
        monthly_summary = MonthlySummary.query.filter_by(
            user_id_hash=psid_hash,
            month=current_month
        ).first()
        
        if not monthly_summary:
            monthly_summary = MonthlySummary()
            monthly_summary.user_id_hash = psid_hash
            monthly_summary.month = current_month
            monthly_summary.total_amount = amount
            monthly_summary.expense_count = 1
            monthly_summary.categories = {category: float(amount)}
            db.session.add(monthly_summary)
        else:
            monthly_summary.total_amount = float(monthly_summary.total_amount or 0) + float(amount)
            monthly_summary.expense_count = (monthly_summary.expense_count or 0) + 1
            
            # Update category breakdown
            categories = monthly_summary.categories or {}
            categories[category] = categories.get(category, 0) + float(amount)
            monthly_summary.categories = categories
            monthly_summary.updated_at = datetime.utcnow()
        
        # Commit transaction
        db.session.commit()
        
        logger.info(f"Expense saved: user={psid_hash[:8]}... mid={mid} amount={amount} category={category}")
        
        return {
            'duplicate': False,
            'idempotent': False,
            'success': True,
            'expense_id': expense.id,
            'amount': float(amount),
            'currency': currency,
            'category': category,
            'merchant': merchant,
            'monthly_total': float(monthly_summary.total_amount),
            'expense_count': monthly_summary.expense_count
        }
        
    except Exception as e:
        logger.error(f"Error in upsert_expense_idempotent: {str(e)}")
        db.session.rollback()
        return {
            'duplicate': False,
            'success': False,
            'error': str(e)
        }

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

def save_expense_idempotent(user_identifier, description, amount, category, currency, platform, original_message, unique_id, db_session=None):
    """
    Legacy compatibility wrapper for save_expense_idempotent.
    Calls the new upsert_expense_idempotent function.
    """
    payload = {
        'amount': amount,
        'currency': currency,
        'category': category,
        'description': description,
        'original_message': original_message
    }
    
    return upsert_expense_idempotent(user_identifier, unique_id, payload)
