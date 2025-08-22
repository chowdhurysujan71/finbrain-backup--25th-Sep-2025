"""
FinBrain Expense Correction Handler
Handles expense corrections with idempotent supersede logic and coach-style confirmations
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from app import db
from models import Expense, User
from parsers.expense import parse_expense, parse_correction_reason, similar_category, similar_merchant
from utils.structured import log_correction_detected, log_correction_no_candidate, log_correction_duplicate, log_correction_applied
from templates.replies import format_correction_no_candidate_reply, format_corrected_reply, format_correction_duplicate_reply
from utils.identity import psid_hash

logger = logging.getLogger("handlers.expense")

def handle_correction(psid_hash_val: str, mid: str, text: str, now: datetime) -> Dict[str, Any]:
    """
    Handle expense correction with supersede logic.
    
    Args:
        psid_hash_val: User's PSID hash
        mid: Message ID for idempotency
        text: Correction message text
        now: Current timestamp
        
    Returns:
        Dict with response text, intent, category, and amount
    """
    start_time = time.time()
    
    try:
        # Step 1: Parse the new target expense from correction message
        target_expense = parse_expense(text, now, correction_context=True)
        
        if not target_expense or not target_expense.get('amount'):
            logger.warning(f"No valid amount found in correction: {text}")
            return {
                'text': "I didn't see a valid amount to correct to. Please try again with the new amount.",
                'intent': 'correction_error',
                'category': None,
                'amount': None
            }
        
        log_correction_detected(psid_hash_val, mid, "CORRECTION", "parsed_target", "SMART_CORRECTIONS", "smart_corrections_v1")
        
        # Step 2: Find candidate expense to correct within 10-minute window
        correction_window = timedelta(minutes=10)
        window_start = now - correction_window
        
        # Query uncorrected expenses for this user within the time window
        candidate_expenses = db.session.query(Expense).filter(
            Expense.user_id == psid_hash_val,
            Expense.created_at >= window_start,
            Expense.superseded_by.is_(None)  # Only uncorrected expenses
        ).order_by(Expense.created_at.desc()).limit(5).all()
        
        if not candidate_expenses:
            # No candidates found - log as new expense and inform user
            log_correction_no_candidate(psid_hash_val, mid, "logged_as_new")
            
            # Save as new expense with normal logging
            new_expense = _create_new_expense(psid_hash_val, mid, target_expense, text, now)
            db.session.add(new_expense)
            
            # Update user totals
            _update_user_totals(psid_hash_val, float(target_expense['amount']))
            
            db.session.commit()
            
            response = format_correction_no_candidate_reply(
                target_expense['amount'], 
                target_expense['currency'], 
                target_expense['category']
            )
            
            return {
                'text': response,
                'intent': 'correction_logged_as_new',
                'category': target_expense['category'],
                'amount': float(target_expense['amount'])
            }
        
        # Step 3: Find best candidate to correct
        best_candidate = _find_best_correction_candidate(candidate_expenses, target_expense)
        
        if not best_candidate:
            # Fallback to most recent expense
            best_candidate = candidate_expenses[0]
        
        # Step 4: Check for duplicate correction attempt (same mid)
        existing_correction = db.session.query(Expense).filter(
            Expense.user_id == psid_hash_val,
            Expense.unique_id.like(f'%{mid}%')
        ).first()
        
        if existing_correction:
            log_correction_duplicate(psid_hash_val, mid)
            response = format_correction_duplicate_reply()
            return {
                'text': response,
                'intent': 'correction_duplicate',
                'category': None,
                'amount': None
            }
        
        # Step 5: Perform supersede operation
        correction_reason = parse_correction_reason(text)
        
        # Create new corrected expense
        new_expense = _create_new_expense(psid_hash_val, mid, target_expense, text, now)
        db.session.add(new_expense)
        db.session.flush()  # Get the new expense ID
        
        # Mark old expense as superseded
        best_candidate.superseded_by = new_expense.id
        best_candidate.corrected_at = now
        best_candidate.corrected_reason = correction_reason
        
        # Update user totals (remove old, add new)
        old_amount = float(best_candidate.amount)
        new_amount = float(target_expense['amount'])
        amount_difference = new_amount - old_amount
        _update_user_totals(psid_hash_val, amount_difference)
        
        # Commit the transaction
        db.session.commit()
        
        # Log successful correction
        log_correction_applied(
            psid_hash_val, mid, best_candidate.id, new_expense.id, 
            old_amount, new_amount, "smart_corrections_v1"
        )
        
        # Generate coach-style confirmation
        response = format_corrected_reply(
            old_amount, best_candidate.currency,
            new_amount, target_expense['currency'],
            target_expense['category'],
            target_expense.get('merchant')
        )
        
        processing_time = (time.time() - start_time) * 1000
        logger.info(f"Correction processed successfully in {processing_time:.2f}ms")
        
        return {
            'text': response,
            'intent': 'correction_applied',
            'category': target_expense['category'],
            'amount': new_amount
        }
        
    except Exception as e:
        logger.error(f"Correction handling error: {e}", exc_info=True)
        db.session.rollback()
        
        return {
            'text': "Sorry, I couldn't process the correction. Please try logging the expense again.",
            'intent': 'correction_error',
            'category': None,
            'amount': None
        }

def _find_best_correction_candidate(candidates: list, target_expense: Dict[str, Any]) -> Optional[Expense]:
    """
    Find the best expense to correct based on category and merchant similarity.
    
    Args:
        candidates: List of potential expenses to correct
        target_expense: Parsed target expense data
        
    Returns:
        Best candidate expense or None if no good match
    """
    if not candidates:
        return None
    
    target_category = target_expense.get('category', '').lower()
    target_merchant = target_expense.get('merchant', '').lower() if target_expense.get('merchant') else None
    
    scored_candidates = []
    
    for candidate in candidates:
        score = 0
        
        # Category similarity (higher weight)
        if similar_category(candidate.category, target_category):
            score += 10
        
        # Merchant similarity (medium weight)  
        candidate_merchant = getattr(candidate, 'merchant', None) or ''
        if target_merchant and similar_merchant(candidate_merchant, target_merchant):
            score += 5
        
        # Recency bonus (most recent gets small bonus)
        if candidate == candidates[0]:  # Most recent
            score += 1
            
        scored_candidates.append((candidate, score))
    
    # Sort by score descending
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Return best candidate if it has a meaningful score, otherwise most recent
    best_candidate, best_score = scored_candidates[0]
    
    if best_score >= 5:  # Has category or merchant match
        return best_candidate
    else:
        # Fall back to most recent if no semantic match
        return candidates[0]

def _create_new_expense(psid_hash_val: str, mid: str, expense_data: Dict[str, Any], original_text: str, now: datetime) -> Expense:
    """
    Create new expense record from parsed data.
    
    Args:
        psid_hash_val: User's PSID hash
        mid: Message ID for uniqueness
        expense_data: Parsed expense data
        original_text: Original message text
        now: Current timestamp
        
    Returns:
        New Expense instance
    """
    expense = Expense()
    expense.user_id = psid_hash_val
    expense.amount = expense_data['amount']
    expense.currency = expense_data.get('currency', 'BDT')
    expense.category = expense_data.get('category', 'general')
    expense.description = expense_data.get('note', original_text)
    expense.date = (expense_data.get('ts_client') or now).date()
    expense.time = (expense_data.get('ts_client') or now).time()
    expense.month = now.strftime('%Y-%m')
    expense.unique_id = f"correction_{mid}_{int(now.timestamp() * 1000)}"
    expense.created_at = now
    expense.platform = 'messenger'
    expense.original_message = original_text[:500]
    
    return expense

def _update_user_totals(psid_hash_val: str, amount_change: float) -> None:
    """
    Update user totals with amount change (can be negative for corrections).
    
    Args:
        psid_hash_val: User's PSID hash
        amount_change: Amount to add/subtract from totals
    """
    user = db.session.query(User).filter_by(user_id_hash=psid_hash_val).first()
    
    if not user:
        # Create user record if doesn't exist
        user = User()
        user.user_id_hash = psid_hash_val
        user.platform = 'messenger'
        user.total_expenses = max(0, amount_change)  # Don't go negative
        user.expense_count = 1 if amount_change > 0 else 0
        user.last_interaction = datetime.utcnow()
        user.last_user_message_at = datetime.utcnow()
        db.session.add(user)
    else:
        # Update existing user
        user.total_expenses = max(0, (user.total_expenses or 0) + Decimal(str(amount_change)))
        user.last_interaction = datetime.utcnow()
        user.last_user_message_at = datetime.utcnow()
        
        # Only increment count for positive changes (new expenses)
        if amount_change > 0:
            user.expense_count = (user.expense_count or 0) + 1