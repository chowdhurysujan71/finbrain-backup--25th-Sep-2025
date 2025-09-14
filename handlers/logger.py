"""
Expense logger handler: Logs expenses to database
"""
from typing import Dict, List
import logging
import time
from datetime import datetime
import backend_assistant as ba
from utils.security import hash_psid

logger = logging.getLogger(__name__)

def handle_log(user_id: str, text: str) -> Dict[str, str]:
    """
    Log expense(s) from user message using unified create_expense function
    Returns dict with 'text' key containing confirmation
    """
    from utils.db import create_expense
    import uuid
    
    try:
        # Parse expense using same deterministic parser as propose_expense API
        parsed_expense = ba.propose_expense(text)
        
        # Check if parsing was successful
        amount_minor = parsed_expense.get('amount_minor')
        category = parsed_expense.get('category')
        
        if not amount_minor or not category:
            return {"text": "I couldn't find an amount to log. Try: 'spent 100 on lunch'"}
        
        # Convert parsed data to expected format
        expenses = [{
            'amount': float(amount_minor) / 100,  # Convert from minor units to float
            'category': str(category),
            'description': parsed_expense.get('description', text)
        }]
        
        logged = []
        total = 0
        user_hash = hash_psid(user_id) if user_id.isdigit() else user_id
        
        # Generate correlation_id at edge for idempotency
        correlation_id = str(uuid.uuid4())
        occurred_at = datetime.now()
        source_message_id = f"chat_{int(time.time() * 1000000)}"
        
        # Use unified create_expense function for each expense
        expense_results = []
        try:
            for exp in expenses:
                result = create_expense(
                    user_id=user_hash,
                    amount=exp['amount'],
                    currency='৳',
                    category=exp['category'],
                    occurred_at=occurred_at,
                    source_message_id=source_message_id,
                    correlation_id=str(uuid.uuid4()),  # Generate unique UUID for each expense
                    notes=exp.get('description') or text
                )
                expense_results.append(result)
                logged.append(f"{exp['amount']:.0f} for {exp['category']}")
                total += exp['amount']
            
        except Exception as e:
            logger.error(f"Unified expense logging failed: {e}")
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
        return {"text": "Unable to log expense. Please try again."}