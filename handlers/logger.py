"""
Expense logger handler: Logs expenses to database
"""
from typing import Dict, List
import logging
import time
from datetime import datetime
from utils.parser import extract_expenses
from utils.security import hash_psid

logger = logging.getLogger(__name__)

def handle_log(user_id: str, text: str) -> Dict[str, str]:
    """
    Log expense(s) from user message
    Returns dict with 'text' key containing confirmation
    """
    from models import Expense
    from app import db
    
    try:
        # Extract expenses from text
        expenses = extract_expenses(text)
        
        if not expenses:
            return {"text": "I couldn't find an amount to log. Try: 'spent 100 on lunch'"}
        
        logged = []
        total = 0
        user_hash = hash_psid(user_id) if user_id.isdigit() else user_id
        
        # Atomic transaction with concurrent-safe user updates
        try:
            from models import User
            from decimal import Decimal
            from sqlalchemy import text as sql_text
            
            # Log each expense first
            for exp in expenses:
                expense = Expense()
                expense.user_id = user_id
                expense.user_id_hash = user_hash
                expense.amount = exp['amount']
                expense.category = exp['category']
                expense.description = exp.get('description', '')
                expense.original_message = text
                expense.date = datetime.now().date()
                expense.time = datetime.now().time()
                expense.month = datetime.now().strftime("%Y-%m")
                expense.platform = "pwa"
                
                # Generate unique ID for idempotency
                try:
                    import uuid
                    expense.unique_id = uuid.uuid4().hex
                except Exception:
                    expense.unique_id = f"fallback_{datetime.now().isoformat()}"
                
                # Set message ID if available - ensure uniqueness for rapid requests
                expense.mid = locals().get("mid") or exp.get("mid") or f"dispatch_{int(time.time() * 1000000)}"
                
                db.session.add(expense)
                logged.append(f"{exp['amount']:.0f} for {exp['category']}")
                total += exp['amount']
            
            # Use PostgreSQL UPSERT for concurrent-safe user totals update
            now_ts = datetime.utcnow()
            db.session.execute(sql_text("""
                INSERT INTO users (user_id_hash, platform, total_expenses, expense_count, last_interaction, last_user_message_at)
                VALUES (:user_hash, 'pwa', :total, :count, :now_ts, :now_ts)
                ON CONFLICT (user_id_hash) DO UPDATE SET
                    total_expenses = COALESCE(users.total_expenses, 0) + :total,
                    expense_count = COALESCE(users.expense_count, 0) + :count,
                    last_interaction = :now_ts,
                    last_user_message_at = :now_ts
            """), {
                'user_hash': user_hash,
                'total': total,
                'count': len(logged),
                'now_ts': now_ts
            })
            
            # Single atomic commit for both expenses and user totals
            db.session.commit()
            
        except Exception as e:
            # Rollback entire transaction on any failure
            db.session.rollback()
            logger.error(f"Atomic expense logging failed: {e}")
            return {"text": "Unable to log expense. Please try again."}
        
        # Format confirmation
        if len(logged) == 1:
            msg = f"✅ Logged: {logged[0]}"
        else:
            msg = f"✅ Logged {len(logged)} expenses totaling {total:.0f} BDT:\n"
            msg += "\n".join(f"• {item}" for item in logged)
        
        # Check for milestone achievements after successful logging
        try:
            from handlers.milestones import check_milestones_after_log
            user_hash = hash_psid(user_id) if user_id.isdigit() else user_id
            milestone_message = check_milestones_after_log(user_hash)
            
            if milestone_message:
                msg += f"\n\n{milestone_message}"
                logger.info(f"Milestone message added for user {user_hash[:8]}...")
            
        except Exception as e:
            logger.warning(f"Milestone check failed: {e}")
            # Don't break expense logging if milestone check fails
        
        # Check for challenge progress after successful logging (Block 6)
        try:
            from handlers.challenge import check_challenge_progress
            user_hash = hash_psid(user_id) if user_id.isdigit() else user_id
            challenge_message = check_challenge_progress(user_hash, text)
            
            if challenge_message:
                msg += f"\n\n{challenge_message}"
                logger.info(f"Challenge message added for user {user_hash[:8]}...")
            
        except Exception as e:
            logger.warning(f"Challenge check failed: {e}")
            # Don't break expense logging if challenge check fails
        
        msg += "\n\nTip: type 'summary' for your spending overview."
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Log handler error: {e}")
        db.session.rollback()
        return {"text": "Unable to log expense. Please try again."}