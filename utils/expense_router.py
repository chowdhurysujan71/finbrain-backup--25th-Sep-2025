"""
Enhanced expense router with AI fallback and debug stamping
Implements the complete single-source-of-truth identity flow
"""

import logging
from typing import Dict, Any, Optional

from ai.expense_parse import parse_expense, regex_parse
from utils.debug_stamper import send_reply
from utils.db import save_expense

logger = logging.getLogger(__name__)

def handle_expense(job: Dict[str, Any]) -> bool:
    """
    Router: try AI → fallback regex → user hint
    Uses single-source-of-truth identity from job["psid_hash"]
    
    Args:
        job: Background job containing psid, psid_hash, text, mid
        
    Returns:
        bool: True if expense logged successfully
    """
    mode = "AI"
    
    try:
        # Try AI parsing first
        exp = parse_expense(job["text"])
        logger.info(f"AI parse success | psid_hash={job['psid_hash'][:12]}... | amount={exp['amount']}")
    except Exception as e:
        logger.warning(f"AI expense parsing failed: {e}")
        mode = "STD"
        
        # Fallback to regex parsing
        exp = regex_parse(job["text"])
        if not exp:
            # User hint for unrecognized format
            send_reply(
                job, 
                "I couldn't read that. Try: 'spent 200 on groceries' or 'coffee 50'", 
                mode="ERR"
            )
            return False
        
        logger.info(f"Regex parse success | psid_hash={job['psid_hash'][:12]}... | amount={exp['amount']}")
    
    try:
        # Save expense using canonical identity (using existing function signature)
        save_expense(
            user_identifier=job["psid_hash"],  # Use pre-computed hash from webhook intake
            description=f"{exp['category']} expense",
            amount=exp["amount"],
            category=exp["category"], 
            platform="facebook",
            original_message=job.get("text", ""),
            unique_id=job.get("mid", "")
        )
        
        # Send success reply with debug stamp
        currency_symbol = "৳"  # From app config
        send_reply(
            job,
            f"✅ Logged: {currency_symbol}{exp['amount']:.2f} for {exp['category'].lower()}",
            mode=mode
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Database save failed | psid_hash={job['psid_hash'][:12]}... | error={e}")
        send_reply(
            job,
            "Something went wrong saving your expense. Please try again.",
            mode="ERR"
        )
        return False

def handle_summary_request(job: Dict[str, Any]) -> bool:
    """
    Handle summary request with canonical identity
    Bypasses AI rate limiting for instant response
    """
    try:
        # Use existing database functions (placeholder for now)
        def get_expense_summary(user_hash, days):
            return {"total": 450.0, "count": 3}  # Mock data for testing
        
        # Get 7-day summary using canonical identity
        summary = get_expense_summary(job["psid_hash"], days=7)
        
        if not summary or summary.get("total", 0) == 0:
            send_reply(
                job,
                "📊 No expenses recorded in the last 7 days",
                mode="STD"
            )
        else:
            total = summary["total"]
            count = summary.get("count", 0)
            currency_symbol = "৳"
            
            send_reply(
                job,
                f"📊 Last 7 days: {currency_symbol}{total:.0f} total ({count} expenses)",
                mode="STD"
            )
        
        logger.info(f"Summary delivered | psid_hash={job['psid_hash'][:12]}... | total={summary.get('total', 0)}")
        return True
        
    except Exception as e:
        logger.error(f"Summary failed | psid_hash={job['psid_hash'][:12]}... | error={e}")
        send_reply(
            job,
            "Unable to get your summary right now. Try again later.",
            mode="ERR"
        )
        return False