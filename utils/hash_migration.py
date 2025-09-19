"""
Safe Hash Migration Utilities

Implements dual-read pattern to handle legacy data that was hashed 
with the old unsalted method while migrating to the new salted approach.

CRITICAL: This prevents data loss during the hash standardization fix.
"""

import logging
import hashlib
import os
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from utils.identity import psid_hash, ensure_hashed as salted_ensure_hashed

logger = logging.getLogger(__name__)

# Metrics tracking
_migration_metrics = {
    'legacy_data_found': 0,
    'successful_migrations': 0,
    'migration_errors': 0
}

def get_legacy_hash(user_identifier: str) -> str:
    """
    Generate the OLD unsalted hash method for backward compatibility
    
    This replicates the old utils.crypto.ensure_hashed() behavior
    before it was fixed to delegate to identity.ensure_hashed()
    """
    return hashlib.sha256(user_identifier.encode('utf-8')).hexdigest()

def dual_read_user_hash(user_identifier: str, db_session: Session, model_class, hash_field: str = 'user_id_hash') -> Optional[Any]:
    """
    Dual-read pattern: Try salted hash first, fallback to legacy hash
    
    Args:
        user_identifier: Raw user ID (PSID, session ID, etc.)
        db_session: SQLAlchemy session
        model_class: Model class to query (User, Expense, etc.)
        hash_field: Field name containing the hash
        
    Returns:
        Found record or None
    """
    if not user_identifier:
        return None
    
    # Method 1: Try new salted hash first (most common case)
    salted_hash = salted_ensure_hashed(user_identifier)
    record = db_session.query(model_class).filter(
        getattr(model_class, hash_field) == salted_hash
    ).first()
    
    if record:
        logger.debug(f"Found record with salted hash for {hash_field}: {salted_hash[:8]}...")
        return record
    
    # Method 2: Try legacy unsalted hash for backward compatibility
    legacy_hash = get_legacy_hash(user_identifier)
    
    # Only try legacy if it's different from salted (avoid duplicate queries)
    if legacy_hash != salted_hash:
        record = db_session.query(model_class).filter(
            getattr(model_class, hash_field) == legacy_hash
        ).first()
        
        if record:
            logger.info(f"Found legacy record for migration: {hash_field}={legacy_hash[:8]}...")
            _migration_metrics['legacy_data_found'] += 1
            
            # Migrate the record to use salted hash
            try:
                migrate_record_hash(record, hash_field, salted_hash, db_session)
                return record
            except Exception as e:
                logger.error(f"Failed to migrate record hash: {e}")
                _migration_metrics['migration_errors'] += 1
                return record  # Return record even if migration failed
    
    # Not found with either hash method
    logger.debug(f"No record found for user_identifier with either hash method")
    return None

def migrate_record_hash(record: Any, hash_field: str, new_hash: str, db_session: Session) -> bool:
    """
    Migrate a single record from legacy hash to salted hash
    
    Args:
        record: Database record to migrate
        hash_field: Field name containing the hash
        new_hash: New salted hash value
        db_session: SQLAlchemy session
        
    Returns:
        True if migration successful, False otherwise
    """
    try:
        old_hash = getattr(record, hash_field)
        
        # Update to new salted hash
        setattr(record, hash_field, new_hash)
        
        # Commit the change
        db_session.commit()
        
        logger.info(f"Migrated {record.__class__.__name__} hash: {old_hash[:8]}... → {new_hash[:8]}...")
        _migration_metrics['successful_migrations'] += 1
        
        return True
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to migrate {record.__class__.__name__} hash: {e}")
        _migration_metrics['migration_errors'] += 1
        return False

def dual_read_user_expenses(user_identifier: str, db_session: Session) -> List[Any]:
    """
    Get all expenses for a user using dual-read pattern
    
    Args:
        user_identifier: Raw user ID
        db_session: SQLAlchemy session
        
    Returns:
        List of expense records
    """
    from models import Expense
    
    if not user_identifier:
        return []
    
    # Try salted hash first
    salted_hash = salted_ensure_hashed(user_identifier)
    expenses = db_session.query(Expense).filter(
        Expense.user_id_hash == salted_hash
    ).all()
    
    if expenses:
        logger.debug(f"Found {len(expenses)} expenses with salted hash")
        return expenses
    
    # Try legacy hash if different
    legacy_hash = get_legacy_hash(user_identifier)
    if legacy_hash != salted_hash:
        expenses = db_session.query(Expense).filter(
            Expense.user_id_hash == legacy_hash
        ).all()
        
        if expenses:
            logger.info(f"Found {len(expenses)} legacy expenses for migration")
            _migration_metrics['legacy_data_found'] += len(expenses)
            
            # Migrate all expenses to salted hash
            for expense in expenses:
                try:
                    migrate_record_hash(expense, 'user_id_hash', salted_hash, db_session)
                except Exception as e:
                    logger.error(f"Failed to migrate expense {expense.id}: {e}")
            
            return expenses
    
    return []

def get_migration_metrics() -> Dict[str, int]:
    """Get current migration metrics for monitoring"""
    return _migration_metrics.copy()

def reset_migration_metrics():
    """Reset migration metrics (useful for testing)"""
    global _migration_metrics
    _migration_metrics = {
        'legacy_data_found': 0,
        'successful_migrations': 0,
        'migration_errors': 0
    }

def log_migration_stats():
    """Log current migration statistics"""
    metrics = get_migration_metrics()
    if metrics['legacy_data_found'] > 0:
        logger.info(f"Hash migration stats: {metrics}")
    return metrics