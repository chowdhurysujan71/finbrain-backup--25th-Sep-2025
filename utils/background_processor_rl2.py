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

logger = logging.getLogger(__name__)

class RL2Processor:
    """RL-2: Graceful non-AI fallback with deterministic rules"""
    
    def __init__(self):
        self.ascii_disclaimer = (
            "NOTE: Taking a quick breather. I can do 2 smart replies per minute per person.\n"
            "OK: I handled that without AI this time.\n"
            "Tip: type \"summary\" for a quick recap."
        )
    
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
                
                # Store expense in database
                self._store_expense(psid, amount, description, category, text)
                
                # RL-2: ASCII-safe response with disclaimer
                response = self.ascii_disclaimer
                
                # Log with RL-2 metadata
                self._log_rl2_job(psid_hash, "expense", handled_by="rules", ai_allowed=False)
                
                return response, "log", category, amount
                
            except Exception as e:
                logger.error(f"RL-2 expense processing error: {str(e)}")
                self._log_rl2_job(psid_hash, "expense_error", handled_by="rules", ai_allowed=False)
                return "Error processing expense without AI.", "error", None, None
        
        # RL-2: No expense pattern matched - help message
        response = "Try: log 250 lunch | 250 lunch | lunch 250"
        self._log_rl2_job(psid_hash, "help", handled_by="rules", ai_allowed=False)
        return response, "help", None, None
    
    def _handle_rate_limited_summary(self, psid: str, psid_hash: str) -> Tuple[str, str, Optional[str], Optional[float]]:
        """
        RL-2: Handle 'summary' command during rate limiting
        Single SQL query, prepend disclaimer, never requeue
        """
        try:
            from app import db
            from models import Expense
            from sqlalchemy import text
            
            # Calculate time windows (today, 7d, 30d)
            now = datetime.now()
            today = now.date()
            seven_days_ago = now - timedelta(days=7)
            thirty_days_ago = now - timedelta(days=30)
            
            # Single optimized SQL query for all summary data
            summary_query = text("""
                SELECT 
                    SUM(CASE WHEN date = :today THEN amount ELSE 0 END) as today_total,
                    SUM(CASE WHEN created_at >= :seven_days THEN amount ELSE 0 END) as week_total,
                    SUM(CASE WHEN created_at >= :thirty_days THEN amount ELSE 0 END) as month_total,
                    category,
                    SUM(CASE WHEN created_at >= :thirty_days THEN amount ELSE 0 END) as category_total
                FROM expenses 
                WHERE user_id = :user_hash
                  AND created_at >= :thirty_days
                GROUP BY category
                ORDER BY category_total DESC
                LIMIT 3
            """)
            
            user_hash = hash_psid(psid)
            results = db.session.execute(summary_query, {
                'today': today,
                'seven_days': seven_days_ago,
                'thirty_days': thirty_days_ago,
                'user_hash': user_hash
            }).fetchall()
            
            if not results or not any(row.category_total for row in results):
                response = (
                    "NOTE: Smart replies are capped at 2/min. Here is your recap without AI:\n"
                    "No expenses found."
                )
            else:
                # Calculate totals from results
                today_total = sum(float(row.today_total or 0) for row in results)
                week_total = sum(float(row.week_total or 0) for row in results)
                month_total = sum(float(row.month_total or 0) for row in results)
                
                # Build top 3 categories
                categories = []
                for row in results[:3]:
                    if row.category_total and float(row.category_total) > 0:
                        categories.append(f"{row.category}: ৳{row.category_total:.0f}")
                
                categories_text = ", ".join(categories[:3]) if categories else "No categories"
                
                # Format response (plain text, <=280 chars)
                response = (
                    f"NOTE: Smart replies are capped at 2/min. Here is your recap without AI:\n"
                    f"Today: ৳{today_total:.0f} | 7d: ৳{week_total:.0f} | 30d: ৳{month_total:.0f}\n"
                    f"Top: {categories_text}"
                )
            
            # RL-2: Log with proper metadata
            self._log_rl2_job(psid_hash, "summary", handled_by="rules", ai_allowed=False)
            
            return response, "summary", None, None
            
        except Exception as e:
            logger.error(f"RL-2 summary processing error: {str(e)}")
            response = (
                "NOTE: Smart replies are capped at 2/min. Here is your recap without AI:\n"
                "Error generating summary."
            )
            self._log_rl2_job(psid_hash, "summary_error", handled_by="rules", ai_allowed=False)
            return response, "summary_error", None, None
    
    def _store_expense(self, psid: str, amount: float, description: str, category: str, original_text: str):
        """Store expense in database with proper user management"""
        from app import db
        from models import Expense, User
        from datetime import datetime
        
        user_hash = hash_psid(psid)
        
        # Create expense record
        expense = Expense()
        expense.user_id = user_hash
        expense.description = description
        expense.amount = amount
        expense.category = category
        expense.currency = '৳'
        expense.month = datetime.now().strftime('%Y-%m')
        expense.unique_id = f"rl2_{int(time.time())}_{hash(original_text)%1000}"
        expense.platform = 'messenger'
        expense.original_message = original_text
        
        # Update or create user record
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
        
        # Save to database atomically
        db.session.add(expense)
        db.session.commit()
    
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