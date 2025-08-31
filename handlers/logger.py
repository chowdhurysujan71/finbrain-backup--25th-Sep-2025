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
        
        # Log each expense
        for exp in expenses:
            expense = Expense()
            expense.user_id = user_id
            expense.user_id_hash = hash_psid(user_id) if user_id.isdigit() else user_id  # Ensure proper hash
            expense.amount = exp['amount']
            expense.category = exp['category']
            expense.description = exp.get('description', '')
            expense.original_message = text
            expense.date = datetime.now().date()
            expense.time = datetime.now().time()
            expense.month = datetime.now().strftime("%Y-%m")
            expense.platform = "messenger"
            
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
        
        db.session.commit()
        
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
        
        msg += "\n\nTip: type 'summary' for your spending overview."
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Log handler error: {e}")
        db.session.rollback()
        return {"text": "Unable to log expense. Please try again."}