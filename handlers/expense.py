"""
FinBrain Expense Correction Handler
Handles expense corrections with idempotent supersede logic and coach-style confirmations
"""

import logging
import re
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from db_base import db
from models import Expense, User
from parsers.expense import parse_expense, extract_all_expenses, parse_correction_reason, similar_category, similar_merchant
from utils.structured import log_correction_detected, log_correction_no_candidate, log_correction_duplicate, log_correction_applied
from templates.replies import format_correction_no_candidate_reply, format_corrected_reply, format_correction_duplicate_reply
from utils.identity import psid_hash

logger = logging.getLogger("handlers.expense")

# Context cache for Q&A intent (2-minute TTL)
_recent_expense_context = {}

def handle_multi_expense_logging(psid_hash_val: str, mid: str, text: str, now: datetime) -> Dict[str, Any]:
    """
    Handle logging of multiple expenses from a single message.
    
    Args:
        psid_hash_val: User's PSID hash
        mid: Message ID for idempotency
        text: Message text containing multiple expenses
        now: Current timestamp
        
    Returns:
        Dict with response text, intent, category, and amount
    """
    start_time = time.time()
    
    try:
        # Extract all expenses from the message
        expenses = extract_all_expenses(text, now)
        
        if not expenses:
            return {
                'text': "I didn't find any valid expenses in that message. Please try again.",
                'intent': 'log_error',
                'category': None,
                'amount': None
            }
        
        if len(expenses) == 1:
            # Single expense - use existing handler
            return _handle_single_expense(psid_hash_val, mid, expenses[0], text, now)
        
        # Multiple expenses - create derived message IDs
        logged_expenses = []
        total_amount = 0
        derived_mids = []
        
        for i, expense_data in enumerate(expenses, 1):
            derived_mid = f"{mid}:{i}"
            derived_mids.append(derived_mid)
            
            # Check for existing expense with this derived mid (idempotency)
            existing = db.session.query(Expense).filter(
                Expense.user_id_hash == psid_hash_val,
                Expense.mid == derived_mid
            ).first()
            
            if existing:
                # Skip duplicate
                continue
                
            # Create new expense
            expense = _create_expense_from_data(psid_hash_val, derived_mid, expense_data, text, now, derived_mid)
            db.session.add(expense)
            
            logged_expenses.append(expense_data)
            total_amount += float(expense_data['amount'])
        
        if not logged_expenses:
            # All were duplicates
            return {
                'text': "I've already logged those expenses from this message.",
                'intent': 'log_duplicate',
                'category': None,
                'amount': None
            }
        
        # Update user totals using concurrent-safe UPSERT
        from sqlalchemy import text as sql_text
        
        db.session.execute(sql_text("""
            INSERT INTO users (user_id_hash, platform, total_expenses, expense_count, last_interaction, last_user_message_at)
            VALUES (:user_hash, 'messenger', :total, :count, :now_ts, :now_ts)
            ON CONFLICT (user_id_hash) DO UPDATE SET
                total_expenses = COALESCE(users.total_expenses, 0) + :total,
                expense_count = COALESCE(users.expense_count, 0) + :count,
                last_interaction = :now_ts,
                last_user_message_at = :now_ts
        """), {
            'user_hash': psid_hash_val,
            'total': total_amount,
            'count': len(logged_expenses),
            'now_ts': now
        })
        
        # Single atomic commit for both expenses and user totals
        db.session.commit()
        
        # Cache context for Q&A (2-minute TTL)
        _cache_expense_context(psid_hash_val, derived_mids, logged_expenses, now)
        
        # Emit telemetry
        logger.info(f"LOG_MULTI: {len(logged_expenses)} expenses, total ৳{total_amount}, mids: {derived_mids}")
        
        # Generate coach-style summary reply
        response = _format_multi_expense_reply(logged_expenses, psid_hash_val)
        
        # Add reminder consent prompt if appropriate
        response = _maybe_add_reminder_prompt(psid_hash_val, response)
        
        return {
            'text': response,
            'intent': 'log_multi',
            'category': 'multiple',
            'amount': total_amount
        }
        
    except Exception as e:
        logger.error(f"Multi-expense handling error: {e}", exc_info=True)
        db.session.rollback()
        
        return {
            'text': "Sorry, I couldn't log those expenses. Please try again.",
            'intent': 'log_error',
            'category': None,
            'amount': None
        }

def handle_qa_intent(psid_hash_val: str, text: str, now: datetime) -> Optional[Dict[str, Any]]:
    """
    Handle Q&A intent for questions like 'did you log my breakfast above?'
    
    Args:
        psid_hash_val: User's PSID hash
        text: Question text
        now: Current timestamp
        
    Returns:
        Response dict if Q&A intent detected, None otherwise
    """
    qa_patterns = [
        r'\b(?:did you|have you)\s+(?:log|logged)\s+(?:my|the)\s+(\w+)',
        r'\b(?:was|is)\s+(?:my|the)\s+(\w+)\s+(?:logged|recorded)',
        r'\b(?:did|do)\s+(?:I|you)\s+(?:log|record)\s+(?:my|the)\s+(\w+)'
    ]
    
    for pattern in qa_patterns:
        match = re.search(pattern, text.lower())
        if match:
            item = match.group(1)  # e.g., "breakfast", "coffee", "uber"
            
            # Check recent context cache
            context = _recent_expense_context.get(psid_hash_val)
            if context and (now - context['timestamp']).total_seconds() <= 120:  # 2 minutes
                # Search for matching item in recent expenses
                for expense in context['expenses']:
                    if (item in expense.get('note', '').lower() or 
                        item in expense.get('category', '').lower()):
                        return {
                            'text': f"Yes—logged ৳{expense['amount']} for {expense['category']}.",
                            'intent': 'qa_confirmed',
                            'category': expense['category'],
                            'amount': float(expense['amount'])
                        }
                
                # Item not found in recent context
                return {
                    'text': f"Not yet—want me to add the {item}?",
                    'intent': 'qa_not_found',
                    'category': None,
                    'amount': None
                }
    
    return None  # Not a Q&A intent

def _handle_single_expense(psid_hash_val: str, mid: str, expense_data: Dict[str, Any], original_text: str, now: datetime) -> Dict[str, Any]:
    """
    Handle logging of a single expense.
    """
    # Check for existing expense (idempotency)
    existing = db.session.query(Expense).filter(
        Expense.user_id_hash == psid_hash_val,
        Expense.unique_id == mid
    ).first()
    
    if existing:
        from templates.replies_ai import format_ai_duplicate_reply, log_reply_banner
        log_reply_banner('LOG_DUPLICATE', psid_hash_val)
        return {
            'text': format_ai_duplicate_reply(),
            'intent': 'log_duplicate',
            'category': existing.category,
            'amount': float(existing.amount)
        }
    
    # Atomic transaction: Create expense AND update user totals together
    try:
        # Create new expense
        expense = _create_expense_from_data(psid_hash_val, mid, expense_data, original_text, now, mid)
        db.session.add(expense)
        
        # Update user totals using concurrent-safe UPSERT
        amount = float(expense_data['amount'])
        from sqlalchemy import text as sql_text
        
        db.session.execute(sql_text("""
            INSERT INTO users (user_id_hash, platform, total_expenses, expense_count, last_interaction, last_user_message_at)
            VALUES (:user_hash, 'messenger', :amount, 1, :now_ts, :now_ts)
            ON CONFLICT (user_id_hash) DO UPDATE SET
                total_expenses = COALESCE(users.total_expenses, 0) + :amount,
                expense_count = COALESCE(users.expense_count, 0) + 1,
                last_interaction = :now_ts,
                last_user_message_at = :now_ts
        """), {
            'user_hash': psid_hash_val,
            'amount': amount,
            'now_ts': now
        })
        
        # Single atomic commit for both expense and user totals
        db.session.commit()
        
    except Exception as e:
        # Rollback entire transaction on any failure
        db.session.rollback()
        logger.error(f"Atomic single expense logging failed: {e}")
        return {
            'text': "Unable to log expense. Please try again.",
            'intent': 'log_error',
            'category': None,
            'amount': None
        }
    
    # Cache context for Q&A
    _cache_expense_context(psid_hash_val, [mid], [expense_data], now)
    
    # Generate AI reply
    from templates.replies_ai import format_ai_single_expense_reply, log_reply_banner
    log_reply_banner('LOG', psid_hash_val)
    response = format_ai_single_expense_reply(
        float(expense_data['amount']), 
        expense_data['category'], 
        expense_data.get('currency', 'BDT')
    )
    
    # Add reminder consent prompt if appropriate
    response = _maybe_add_reminder_prompt(psid_hash_val, response)
    
    return {
        'text': response,
        'intent': 'log_single',
        'category': expense_data['category'],
        'amount': amount
    }

def _create_expense_from_data(psid_hash_val: str, unique_id: str, expense_data: Dict[str, Any], original_text: str, now: datetime, mid: Optional[str] = None) -> Expense:
    """
    Create Expense record from parsed expense data.
    """
    from utils.categories import normalize_category
    
    expense = Expense()
    expense.user_id = psid_hash_val
    expense.amount = expense_data['amount']
    expense.currency = expense_data.get('currency', 'BDT')
    expense.category = normalize_category(expense_data.get('category'))
    expense.description = expense_data.get('note', original_text)
    expense.date = (expense_data.get('ts_client') or now).date()
    expense.time = (expense_data.get('ts_client') or now).time()
    expense.month = now.strftime('%Y-%m')
    expense.unique_id = unique_id
    expense.mid = mid or unique_id or 'unknown'  # Use mid for idempotency, fallback to unique_id
    expense.created_at = now
    expense.platform = 'messenger'
    expense.original_message = original_text[:500]
    
    return expense

def _format_multi_expense_reply(expenses: list, psid_hash_val: str) -> str:
    """
    Format AI-style reply for multiple expense logging.
    """
    from templates.replies_ai import format_ai_multi_expense_reply, log_reply_banner
    log_reply_banner('LOG_MULTI', psid_hash_val)
    
    total_amount = sum(float(exp['amount']) for exp in expenses)
    return format_ai_multi_expense_reply(expenses, total_amount)
    
    # Group by category for cleaner display
    summary_parts = []
    for expense in expenses:
        summary_parts.append(f"৳{expense['amount']} {expense['category']}")
    
    summary = "; ".join(summary_parts)
    return f"✅ Logged: {summary}. Type 'summary' to see your week."

def _cache_expense_context(psid_hash_val: str, mids: list, expenses: list, timestamp: datetime):
    """
    Cache recent expense context for Q&A intent (2-minute TTL).
    """
    _recent_expense_context[psid_hash_val] = {
        'mids': mids,
        'expenses': expenses,
        'timestamp': timestamp
    }
    
    # Clean up old cache entries (basic cleanup)
    cutoff = timestamp - timedelta(minutes=3)
    keys_to_remove = []
    for key, context in _recent_expense_context.items():
        if context['timestamp'] < cutoff:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del _recent_expense_context[key]

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
        
        log_correction_detected(psid_hash_val, text, target_expense)
        
        # Step 2: Find candidate expense to correct within 10-minute window
        correction_window = timedelta(minutes=10)
        window_start = now - correction_window
        
        # Query uncorrected expenses for this user within the time window
        candidate_expenses = db.session.query(Expense).filter(
            Expense.user_id_hash == psid_hash_val,
            Expense.created_at >= window_start,
            Expense.superseded_by.is_(None)  # Only uncorrected expenses
        ).order_by(Expense.created_at.desc()).limit(5).all()
        
        if not candidate_expenses:
            # No candidates found - log as new expense and inform user
            log_correction_no_candidate(psid_hash_val, mid, "logged_as_new")
            
            # Save as new expense with normal logging
            new_expense = _create_new_expense(psid_hash_val, mid, target_expense, text, now, mid)
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
            Expense.user_id_hash == psid_hash_val,
            Expense.unique_id.like(f'%{mid}%')
        ).first()
        
        if existing_correction:
            log_correction_duplicate(psid_hash_val, mid, existing_correction.id)
            response = format_correction_duplicate_reply()
            return {
                'text': response,
                'intent': 'correction_duplicate',
                'category': None,
                'amount': None
            }
        
        # Step 5: Perform supersede operation
        correction_reason = parse_correction_reason(text)
        
        # Create corrected expense data with smart categorization logic
        # Prioritize re-analyzed category from correction text over inherited category
        new_category = target_expense.get('category')
        from utils.categories import normalize_category
        if not new_category or normalize_category(new_category) == 'uncategorized':
            # If correction didn't detect category or detected generic, inherit from original
            new_category = best_candidate.category
        
        corrected_expense_data = {
            'amount': target_expense['amount'],
            'category': new_category,
            'currency': target_expense.get('currency') or best_candidate.currency,
            'merchant': target_expense.get('merchant') or getattr(best_candidate, 'merchant', None),
            'note': target_expense.get('note') or text
        }
        
        # Create new corrected expense  
        new_expense = _create_new_expense(psid_hash_val, mid, corrected_expense_data, text, now, mid)
        db.session.add(new_expense)
        db.session.flush()  # Get the new expense ID
        
        # Mark old expense as superseded
        best_candidate.superseded_by = new_expense.id
        best_candidate.corrected_at = now
        best_candidate.corrected_reason = correction_reason
        
        # Update user totals (remove old, add new)
        old_amount = float(best_candidate.amount)
        new_amount = float(corrected_expense_data['amount'])
        amount_difference = new_amount - old_amount
        _update_user_totals(psid_hash_val, amount_difference)
        
        # Commit the transaction
        db.session.commit()
        
        # Log successful correction
        log_correction_applied(
            psid_hash_val, mid, best_candidate.id, new_expense.id, 
            {"old_amount": old_amount, "new_amount": new_amount}
        )
        
        # Generate coach-style confirmation
        response = format_corrected_reply(
            old_amount, best_candidate.currency,
            Decimal(str(new_amount)), corrected_expense_data['currency'],
            corrected_expense_data['category'],
            corrected_expense_data.get('merchant')
        )
        
        processing_time = (time.time() - start_time) * 1000
        logger.info(f"Correction processed successfully in {processing_time:.2f}ms")
        
        return {
            'text': response,
            'intent': 'correction_applied',
            'category': corrected_expense_data['category'],
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
    
    target_category = (target_expense.get('category') or '').lower()
    target_merchant = (target_expense.get('merchant') or '').lower() if target_expense.get('merchant') else None
    
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

def _create_new_expense(psid_hash_val: str, mid: str, expense_data: Dict[str, Any], original_text: str, now: datetime, message_id: Optional[str] = None) -> Expense:
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
    from utils.categories import normalize_category
    
    expense = Expense()
    expense.user_id = psid_hash_val
    expense.amount = expense_data['amount']
    expense.currency = expense_data.get('currency', 'BDT')
    expense.category = normalize_category(expense_data.get('category'))
    expense.description = expense_data.get('note', original_text)
    expense.date = (expense_data.get('ts_client') or now).date()
    expense.time = (expense_data.get('ts_client') or now).time()
    expense.month = now.strftime('%Y-%m')
    expense.unique_id = f"correction_{mid}_{int(now.timestamp() * 1000)}"
    expense.mid = message_id or f"correction_{mid}_{int(now.timestamp() * 1000)}" or 'unknown'  # Use message_id for idempotency
    expense.created_at = now
    expense.platform = 'messenger'
    expense.original_message = original_text[:500]
    
    return expense

def _maybe_add_reminder_prompt(psid_hash_val: str, response: str) -> str:
    """
    Conditionally add reminder consent prompt after expense logging.
    Only prompts if user doesn't have reminders enabled and hasn't been asked recently.
    
    Args:
        psid_hash_val: User's PSID hash
        response: Current response text
        
    Returns:
        Response with optional reminder prompt
    """
    try:
        user = db.session.query(User).filter_by(user_id_hash=psid_hash_val).first()
        
        if not user:
            return response
        
        # Don't prompt if already has reminders enabled
        if user.reminder_preference != 'none':
            return response
        
        # Don't prompt if we already asked recently (avoid spam)
        if user.last_reminder_sent:
            hours_since_last = (datetime.utcnow() - user.last_reminder_sent).total_seconds() / 3600
            if hours_since_last < 72:  # Don't ask again for 3 days
                return response
        
        # Don't prompt very new users (let them get comfortable first)
        if user.expense_count < 3:
            return response
        
        # Add prompt occasionally (not every time)
        import random
        if random.random() < 0.3:  # 30% chance to show prompt
            if len(response) + 50 <= 280:  # Ensure we stay under character limit
                return f"{response}\n\nWant me to check in with you tomorrow evening?"
        
        return response
        
    except Exception as e:
        logger.error(f"Error adding reminder prompt: {e}")
        return response

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