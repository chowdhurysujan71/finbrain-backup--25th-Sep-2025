"""
Expense editing and audit trail functionality for Phase E
Implements "Edit Last Expense" with complete audit trail and idempotency
"""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from flask import request

from models import Expense, ExpenseEdit, User
from db_base import db

logger = logging.getLogger(__name__)

class ExpenseEditor:
    """Handles expense editing with audit trail and idempotency"""
    
    def __init__(self):
        self.duplicate_time_window = 5  # minutes
        
    def get_last_expense(self, user_id_hash: str) -> Optional[Expense]:
        """Get user's most recent expense"""
        try:
            return Expense.query.filter_by(
                user_id_hash=user_id_hash
            ).order_by(Expense.created_at.desc()).first()
        except Exception as e:
            logger.error(f"Error getting last expense: {e}")
            return None
    
    def edit_expense(
        self, 
        expense_id: int, 
        editor_user_id: str,
        new_amount: Optional[float] = None,
        new_category: Optional[str] = None, 
        new_description: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Edit an expense with complete audit trail
        
        Args:
            expense_id: ID of expense to edit
            editor_user_id: User making the edit
            new_amount: New amount (if changing)
            new_category: New category (if changing)
            new_description: New description (if changing) 
            reason: Reason for edit (optional)
            
        Returns:
            Dict with success status and details
        """
        try:
            # Get current expense
            expense = Expense.query.get(expense_id)
            if not expense:
                return {"success": False, "error": "Expense not found"}
            
            # Verify user authorization
            if expense.user_id_hash != editor_user_id:
                return {"success": False, "error": "Unauthorized - can only edit your own expenses"}
            
            # Calculate checksums for integrity
            old_checksum = self._calculate_expense_checksum(expense)
            
            # Determine what's changing
            changes = {}
            edit_type = []
            
            if new_amount is not None and float(new_amount) != float(expense.amount):
                changes['amount'] = (float(expense.amount), float(new_amount))
                edit_type.append('amount')
            
            if new_category and new_category != expense.category:
                changes['category'] = (expense.category, new_category)
                edit_type.append('category')
            
            if new_description and new_description != expense.description:
                changes['description'] = (expense.description, new_description)
                edit_type.append('description')
            
            if not changes:
                return {"success": True, "message": "No changes detected", "changes": {}}
            
            # Check for duplicate edits (idempotency)
            if self._is_duplicate_edit(expense_id, changes):
                return {"success": True, "message": "Duplicate edit detected - no action taken", "changes": changes}
            
            # Apply changes to expense
            old_values = {}
            if 'amount' in changes:
                old_values['amount'] = expense.amount
                expense.amount = changes['amount'][1]
            
            if 'category' in changes:
                old_values['category'] = expense.category  
                expense.category = changes['category'][1]
            
            if 'description' in changes:
                old_values['description'] = expense.description
                expense.description = changes['description'][1]
            
            # Update metadata
            expense.updated_at = datetime.utcnow()
            
            # Calculate new checksum
            new_checksum = self._calculate_expense_checksum(expense)
            
            # Create audit entry
            audit_entry = ExpenseEdit(
                expense_id=expense_id,
                editor_user_id=editor_user_id,
                edited_at=datetime.utcnow(),
                old_amount=old_values.get('amount'),
                old_category=old_values.get('category'),
                old_memo=old_values.get('description'),
                new_amount=expense.amount if 'amount' in changes else None,
                new_category=expense.category if 'category' in changes else None,
                new_memo=expense.description if 'description' in changes else None,
                reason=reason or f"User correction via {'&'.join(edit_type)} edit",
                edit_type='_'.join(edit_type) if edit_type else 'no_change',
                checksum_before=old_checksum,
                checksum_after=new_checksum,
                audit_session_id=str(uuid.uuid4()),
                client_info=self._get_client_info(),
                source='manual_form'
            )
            
            # Commit changes
            db.session.add(audit_entry)
            db.session.commit()
            
            # PHASE F GROWTH TELEMETRY: Track expense_edited event (fail-safe)
            try:
                from utils.telemetry import TelemetryTracker
                TelemetryTracker.track_expense_edited(
                    user_id_hash=editor_user_id,
                    expense_id=expense_id
                )
            except Exception as e:
                # Fail-safe: telemetry errors never break expense editing
                logger.debug(f"Expense edit telemetry tracking failed: {e}")
            
            logger.info(f"Expense {expense_id} edited by {editor_user_id[:8]}... - changes: {list(changes.keys())}")
            
            return {
                "success": True,
                "message": f"Expense updated successfully ({', '.join(edit_type)})",
                "changes": changes,
                "audit_id": audit_entry.id,
                "expense": {
                    "id": expense.id,
                    "amount": float(expense.amount),
                    "category": expense.category,
                    "description": expense.description,
                    "updated_at": expense.updated_at.isoformat()
                }
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error editing expense {expense_id}: {e}")
            return {"success": False, "error": f"Edit failed: {str(e)}"}
    
    def _calculate_expense_checksum(self, expense: Expense) -> str:
        """Calculate SHA-256 checksum of expense state for integrity verification"""
        data = f"{expense.amount}|{expense.category}|{expense.description}|{expense.created_at}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _is_duplicate_edit(self, expense_id: int, changes: Dict) -> bool:
        """Check if this edit is a duplicate of a recent edit attempt"""
        try:
            # Look for recent edits within time window
            cutoff_time = datetime.utcnow() - timedelta(minutes=self.duplicate_time_window)
            
            recent_edit = ExpenseEdit.query.filter(
                ExpenseEdit.expense_id == expense_id,
                ExpenseEdit.edited_at >= cutoff_time
            ).order_by(ExpenseEdit.edited_at.desc()).first()
            
            if not recent_edit:
                return False
            
            # Check if the intended changes match the recent edit
            for field, (old_val, new_val) in changes.items():
                if field == 'amount':
                    if recent_edit.new_amount and float(recent_edit.new_amount) == float(new_val):
                        continue
                elif field == 'category':
                    if recent_edit.new_category == new_val:
                        continue
                elif field == 'description':
                    if recent_edit.new_memo == new_val:
                        continue
                return False  # This change doesn't match recent edit
            
            return True  # All changes match recent edit
            
        except Exception as e:
            logger.error(f"Error checking duplicate edit: {e}")
            return False
    
    def _get_client_info(self) -> Dict[str, Any]:
        """Get client information for audit trail"""
        try:
            # Hash IP address for privacy
            ip = request.remote_addr or 'unknown'
            ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
            
            return {
                "ip_hash": ip_hash,
                "user_agent": request.headers.get('User-Agent', 'unknown')[:100],
                "timestamp": datetime.utcnow().isoformat(),
                "method": request.method,
                "endpoint": request.endpoint
            }
        except:
            return {"error": "Could not capture client info"}
    
    def get_edit_history(self, expense_id: int, user_id_hash: str) -> List[Dict]:
        """Get edit history for an expense"""
        try:
            # Verify user owns the expense
            expense = Expense.query.get(expense_id)
            if not expense or expense.user_id_hash != user_id_hash:
                return []
            
            edits = ExpenseEdit.query.filter_by(
                expense_id=expense_id
            ).order_by(ExpenseEdit.edited_at.desc()).all()
            
            return [{
                "id": edit.id,
                "edited_at": edit.edited_at.isoformat(),
                "edit_type": edit.edit_type,
                "reason": edit.reason,
                "changes": {
                    "amount": {"old": float(edit.old_amount) if edit.old_amount else None, 
                              "new": float(edit.new_amount) if edit.new_amount else None},
                    "category": {"old": edit.old_category, "new": edit.new_category},
                    "description": {"old": edit.old_memo, "new": edit.new_memo}
                }
            } for edit in edits]
            
        except Exception as e:
            logger.error(f"Error getting edit history: {e}")
            return []

# Global instance
expense_editor = ExpenseEditor()

def edit_last_expense(user_id_hash: str, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to edit user's last expense
    
    Args:
        user_id_hash: User identifier
        **kwargs: Edit parameters (new_amount, new_category, new_description, reason)
        
    Returns:
        Dict with edit results
    """
    last_expense = expense_editor.get_last_expense(user_id_hash)
    if not last_expense:
        return {"success": False, "error": "No recent expense found to edit"}
    
    return expense_editor.edit_expense(
        expense_id=last_expense.id,
        editor_user_id=user_id_hash,
        **kwargs
    )