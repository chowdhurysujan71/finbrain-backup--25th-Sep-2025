"""
RL-2 Graceful non-AI fallback system with ASCII-safe disclaimers
Clean implementation of rate-limited message processing
"""
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from utils.security import hash_psid
from utils.parser import parse_expense
from utils.categories import categorize_expense
from utils.logger import get_request_id
from utils.textutil import get_rl2_disclaimer, get_rl2_summary_prefix, normalize

logger = logging.getLogger(__name__)

class RL2Processor:
    """RL-2: Graceful non-AI fallback with deterministic rules"""
    
    def __init__(self):
        self.ascii_disclaimer = get_rl2_disclaimer()
    
    def process_rate_limited_message(self, text: str, psid: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """
        RL-2: Handle message when AI is rate-limited
        Returns: (response_text, intent, category, amount)
        
        Rules:
        - Try deterministic expense patterns: "log <amount> <note>", "<amount> <note>", "<note> <amount>"
        - If "summary": return deterministic summary with disclaimer
        - Plain text only (<=280 chars, no emojis)
        - Set handled_by="rules", ai_allowed=false, job_status="done"
        - Never requeue
        """
        psid_hash = hash_psid(psid)
        
        # RL-2: Handle "summary" command during rate limiting
        if text.strip().lower() == "summary":
            return self._handle_rate_limited_summary(psid, psid_hash)
        
        # RL-2: Try deterministic rules for expense parsing
        parsed_expense = parse_expense(text)
        if parsed_expense:
            try:
                amount, description = parsed_expense
                category = categorize_expense(description)
                
                # Store expense in database (never throws, handles constraints)
                self._store_expense(psid, amount, description, category, text)
                
                # RL-2: ASCII-safe response with disclaimer (sanitized for Facebook API)
                response = normalize(self.ascii_disclaimer)
                
                # Log with RL-2 metadata (never throws)
                self._log_rl2_job(psid_hash, "expense", handled_by="rules", ai_allowed=False)
                
                return response, "log", category, amount
                
            except Exception as e:
                logger.error(f"RL-2 expense processing error: {str(e)}")
                self._log_rl2_job(psid_hash, "expense_error", handled_by="rules", ai_allowed=False)
                return "Error processing expense without AI.", "error", None, None
        
        # RL-2: No expense pattern matched - help message (sanitized)
        response = normalize("Try: log 250 lunch | 250 lunch | lunch 250")
        self._log_rl2_job(psid_hash, "help", handled_by="rules", ai_allowed=False)
        return response, "help", None, None
    

    
    def _handle_rate_limited_summary(self, psid: str, psid_hash: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """
        RL-2: Handle 'summary' command during rate limiting
        Always reply, always ack, never requeue - even on SQL errors
        """
        response = f"{get_rl2_summary_prefix()}\nNo expenses found."
        
        try:
            from app import db
            from models import Expense
            from sqlalchemy import text
            
            # Robust SQL query with NULL safety and error handling
            user_hash = hash_psid(psid)
            
            # Simplified query to avoid multi-join issues
            try:
                # Safe query with explicit NULL handling
                simple_query = text("""
                    SELECT 
                        COALESCE(SUM(amount), 0) as total,
                        COUNT(*) as count,
                        category
                    FROM expenses 
                    WHERE user_id = :user_hash
                      AND created_at >= NOW() - INTERVAL '30 days'
                    GROUP BY category
                    ORDER BY total DESC
                    LIMIT 3
                """)
                
                results = db.session.execute(simple_query, {'user_hash': user_hash}).fetchall()
                
                if results and any(float(row.total or 0) > 0 for row in results):
                    total_30d = sum(float(row.total or 0) for row in results)
                    top_categories = []
                    
                    for row in results[:3]:
                        if row.total and float(row.total) > 0:
                            cat_name = row.category or 'other'
                            top_categories.append(f"{cat_name}: ৳{float(row.total):.0f}")
                    
                    categories_text = ", ".join(top_categories) if top_categories else "No categories"
                    
                    # Format safe response (ASCII only, <=280 chars)
                    response = (
                        f"{get_rl2_summary_prefix()}\n"
                        f"30d total: ৳{total_30d:.0f}\n"
                        f"Top: {categories_text}"
                    )
                
            except Exception as sql_error:
                # SQL failed - still return valid response
                logger.error(f"RL-2 SQL error (non-blocking): {str(sql_error)}")
                # Keep default "No expenses found" response
                
        except Exception as outer_error:
            # Any other error - still return valid response
            logger.error(f"RL-2 summary outer error (non-blocking): {str(outer_error)}")
            # Keep default response
        
        # ALWAYS log completion - never let errors prevent this
        try:
            self._log_rl2_job(psid_hash, "summary", handled_by="rules", ai_allowed=False)
        except Exception as log_error:
            logger.error(f"RL-2 logging error (non-blocking): {str(log_error)}")
        
        # ALWAYS return valid response tuple (sanitized)
        return normalize(response), "summary", None, None
    
    def _store_expense(self, psid: str, amount: float, description: str, category: str, original_text: str):
        """
        Store expense in database with robust error handling
        Never throws - constraint violations are logged but don't block UX
        """
        try:
            from app import db
            from models import Expense, User
            from datetime import datetime
            import random
            
            user_hash = hash_psid(psid)
            
            # Create expense record with collision-resistant unique_id
            expense = Expense()
            expense.user_id = user_hash
            expense.description = description
            expense.amount = amount
            expense.category = category
            expense.currency = '৳'
            expense.month = datetime.now().strftime('%Y-%m')
            # More robust unique ID to avoid constraint violations
            expense.unique_id = f"rl2_{int(time.time() * 1000)}_{random.randint(1000, 9999)}_{abs(hash(original_text)) % 10000}"
            expense.platform = 'messenger'
            expense.original_message = original_text[:500]  # Truncate to avoid length issues
            
            try:
                # Update or create user record with constraint safety
                user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
                if not user:
                    user = User()
                    user.user_id_hash = user_hash
                    user.platform = 'messenger'
                    user.last_user_message_at = datetime.utcnow()
                    db.session.add(user)
                else:
                    user.last_user_message_at = datetime.utcnow()
                
                user.total_expenses = (user.total_expenses or 0) + amount
                user.expense_count = (user.expense_count or 0) + 1
                user.last_interaction = datetime.utcnow()
                
                # Atomic save with rollback on constraint violation
                db.session.add(expense)
                db.session.commit()
                
                logger.debug(f"RL-2 expense stored: {amount} {description}")
                
            except Exception as db_error:
                # Database constraint violation - rollback and log but don't throw
                try:
                    db.session.rollback()
                except:
                    pass
                
                logger.warning(f"RL-2 DB constraint violation (non-blocking): {str(db_error)}")
                # UX continues normally - user gets acknowledgment regardless
                
        except Exception as outer_error:
            # Any other storage error - log but never throw
            logger.error(f"RL-2 storage error (non-blocking): {str(outer_error)}")
            # UX continues - expense might not be stored but user gets response
    
    def _log_rl2_job(self, psid_hash: str, intent: str, handled_by: str, ai_allowed: bool) -> None:
        """
        RL-2: Log job processing with required metadata
        Log: {rid, psid_hash, ai_allowed, reason, handled_by, job_status, window_reset_at}
        """
        try:
            # Calculate window reset time (next minute boundary)
            now = datetime.now(timezone.utc)
            window_reset_at = (now + timedelta(seconds=60)).replace(second=0, microsecond=0)
            
            # RL-2 structured logging
            log_data = {
                "rid": get_request_id(),
                "psid_hash": psid_hash,
                "ai_allowed": ai_allowed,
                "reason": "rate_limited" if not ai_allowed else "ok",
                "handled_by": handled_by,
                "job_status": "done",  # RL-2: Always mark as done, never requeue
                "window_reset_at": window_reset_at.isoformat(),
                "intent": intent,
                "timestamp": now.isoformat()
            }
            
            logger.info(f"RL-2 job completed: {json.dumps(log_data)}")
            
        except Exception as e:
            logger.error(f"RL-2 logging error: {str(e)}")

# Create RL-2 processor instance
rl2_processor = RL2Processor()