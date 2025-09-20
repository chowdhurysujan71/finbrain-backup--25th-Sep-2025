"""
🚨 DEPRECATED EXPENSE WRITERS - ARCHIVED FOR REFERENCE ONLY
=============================================================

These functions violated the single writer principle and have been removed
from the active codebase. They are preserved here for reference only.

DANGER: Do not restore these functions. They bypass security controls.
Use backend_assistant.add_expense() as the canonical single writer.

Removal Date: 2025-09-20
Reason: Single writer principle violation
Replacement: backend_assistant.add_expense()
"""

# Archived deprecated functions from utils/db.py (lines 10-175)
def create_expense_DEPRECATED_ARCHIVED():
    """
    This function has been removed for violating single writer principle.
    Use backend_assistant.add_expense() instead.
    """
    raise NotImplementedError("DEPRECATED: Use backend_assistant.add_expense()")

def save_expense_DEPRECATED_ARCHIVED():
    """
    This function has been removed for violating single writer principle.
    Use backend_assistant.add_expense() instead.
    """
    raise NotImplementedError("DEPRECATED: Use backend_assistant.add_expense()")

def upsert_expense_idempotent_DEPRECATED_ARCHIVED():
    """
    This function has been removed for violating single writer principle.
    Use backend_assistant.add_expense() instead.
    """
    raise NotImplementedError("DEPRECATED: Use backend_assistant.add_expense()")

def save_expense_idempotent_DEPRECATED_ARCHIVED():
    """
    This function has been removed for violating single writer principle.
    Use backend_assistant.add_expense() instead.
    """
    raise NotImplementedError("DEPRECATED: Use backend_assistant.add_expense()")