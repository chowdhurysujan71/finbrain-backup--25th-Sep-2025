"""
SQLAlchemy Event Guard: Runtime protection for single writer principle
Prevents any direct Expense model inserts that bypass backend_assistant.add_expense()
"""

import logging
import contextvars
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Context variable to track canonical writer context
_canonical_writer_context = contextvars.ContextVar('canonical_writer_active', default=False)

class SingleWriterGuard:
    """Runtime guard to enforce single writer principle via SQLAlchemy events"""
    
    def __init__(self):
        self._initialized = False
    
    def initialize(self, db):
        """Initialize the event listener for Expense model"""
        if self._initialized:
            return
            
        from models import Expense
        
        # Register before_insert event listener
        event.listen(Expense, 'before_insert', self._check_canonical_writer)
        
        self._initialized = True
        logger.info("✓ Single Writer Guard initialized - runtime protection active")
    
    def _check_canonical_writer(self, mapper, connection, target):
        """Event handler: Check if insert is from canonical writer"""
        # Check if we're in canonical writer context
        if not _canonical_writer_context.get(False):
            # Get stack trace info for security logging
            import traceback
            stack_info = ''.join(traceback.format_stack()[-3:-1])  # Get calling context
            
            # Log security violation with structured data
            logger.error(
                "SECURITY_VIOLATION: Direct Expense insert blocked by runtime guard",
                extra={
                    "violation_type": "single_writer_bypass_attempt",
                    "model": "Expense",
                    "user_id_hash": getattr(target, 'user_id_hash', 'unknown')[:8] + "...",
                    "amount_minor": getattr(target, 'amount_minor', 'unknown'),
                    "category": getattr(target, 'category', 'unknown'),
                    "stack_trace": stack_info
                }
            )
            
            # Block the operation
            raise RuntimeError(
                "Single-writer violation: Direct Expense insert blocked. "
                "Use backend_assistant.add_expense() instead."
            )
    
    def set_canonical_context(self):
        """Context manager: Mark current context as canonical writer"""
        return _CanonicalWriterContext()

class _CanonicalWriterContext:
    """Context manager for canonical writer operations"""
    
    def __enter__(self):
        self._token = _canonical_writer_context.set(True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _canonical_writer_context.reset(self._token)

# Global instance
single_writer_guard = SingleWriterGuard()

def enable_single_writer_protection(db):
    """Enable runtime protection for single writer principle"""
    single_writer_guard.initialize(db)

def canonical_writer_context():
    """Get context manager for canonical writer operations"""
    return single_writer_guard.set_canonical_context()