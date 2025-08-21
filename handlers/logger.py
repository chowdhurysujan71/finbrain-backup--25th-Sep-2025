"""
Expense logger handler: Logs expenses to database
"""
from typing import Dict, List
import logging
from datetime import datetime
from utils.parser import extract_expenses
from utils.user_manager import resolve_user_id as ensure_hashed

logger = logging.getLogger(__name__)

def handle_log(user_id: str, text: str) -> Dict[str, str]:
    """
    Log expense(s) from user message
    Returns dict with 'text' key containing confirmation
    """
    try:
        # Extract expenses from text
        expenses = extract_expenses(text)
        
        if not expenses:
            return {"text": "I couldn't find an amount to log. Try: 'spent 100 on lunch'"}
        
        from models import Expense
        from app import db
        
        logged = []
        total = 0
        
        # Log each expense
        for exp in expenses:
            expense = Expense(
                user_id=user_id,
                amount=exp['amount'],
                category=exp['category'],
                description=exp.get('description', ''),
                original_message=text
            )
            
            # Ensure month is derived from date
            if not hasattr(expense, 'date') or expense.date is None:
                expense.date = datetime.now().date()
            if not hasattr(expense, 'time') or expense.time is None:
                expense.time = datetime.now().time()
            if not hasattr(expense, 'month') or expense.month is None:
                expense.month = expense.date.strftime("%Y-%m")
            
            # Ensure unique_id is set (critical for DB constraint)
            if not hasattr(expense, 'unique_id') or expense.unique_id is None:
                # Prefer Facebook message ID for idempotency, fallback to UUID
                uid = locals().get("mid") or exp.get("mid")
                if not uid:
                    try:
                        import uuid
                        uid = uuid.uuid4().hex
                    except Exception:
                        uid = f"fallback_{datetime.now().isoformat()}"
                expense.unique_id = uid
            
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
        
        msg += "\n\nTip: type 'summary' for your spending overview."
        
        return {"text": msg}
        
    except Exception as e:
        logger.error(f"Log handler error: {e}")
        db.session.rollback()
        return {"text": "Unable to log expense. Please try again."}