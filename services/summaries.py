# services/summaries.py
"""
Deterministic summary services that provide expense roll-ups and formatting
"""
import logging
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

def build_user_summary(psid: str, start: datetime, end: datetime):
    """
    Return dict like:
    {
      "range": {"start": start.isoformat(), "end": end.isoformat()},
      "total": 720.0,
      "by_category": {"groceries": 120.0, "transport": 100.0, "shopping": 500.0}
    }
    """
    try:
        rows = fetch_expense_totals(psid, start, end)
        by_cat = {}
        grand = 0.0
        
        for r in rows:
            amt = float(r["total"])
            category = r["category"] or "uncategorized"
            by_cat[category] = by_cat.get(category, 0.0) + amt
            grand += amt
            
        if grand == 0.0:
            return None
            
        return {
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "total": grand, 
            "by_category": by_cat
        }
    except Exception as e:
        logger.error(f"Error building user summary: {e}")
        return None

def format_summary_text(rollup: dict) -> str:
    """Format summary rollup as readable text"""
    try:
        total = rollup["total"]
        parts = [f"Last 7 days: {total:.0f} BDT total"]
        
        if rollup["by_category"]:
            cats = " • ".join(
                f"{k} {v:.0f}" 
                for k, v in sorted(rollup["by_category"].items(), key=lambda kv: -kv[1])
            )
            parts.append(cats)
            
        return " • ".join(parts)
    except Exception as e:
        logger.error(f"Error formatting summary text: {e}")
        return "Unable to format summary."

def fetch_expense_totals(psid: str, start: datetime, end: datetime):
    """Fetch expense totals from database for given timeframe"""
    try:
        from models import Expense
        from utils.identity import ensure_hashed
        
        # Use consistent hashing
        user_hash = ensure_hashed(psid)
        
        # Query database for expenses in timeframe
        expenses = Expense.query.filter(
            Expense.user_id_hash == user_hash,
            Expense.created_at >= start,
            Expense.created_at <= end
        ).all()
        
        # Aggregate by category
        rows = []
        category_totals = defaultdict(float)
        
        for expense in expenses:
            category_totals[expense.category] += float(expense.amount)
        
        # Convert to expected format
        for category, total in category_totals.items():
            rows.append({"category": category, "total": total})
            
        return rows
        
    except Exception as e:
        logger.error(f"Error fetching expense totals: {e}")
        return []