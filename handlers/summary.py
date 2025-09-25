"""
Summary handler: Provides expense summaries without AI
"""
import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

def month_bounds(now=None, tz=UTC) -> tuple[datetime, datetime]:
    """Get start and end of current month"""
    now = now or datetime.now(tz)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year+1, month=1)
    else:
        end = start.replace(month=start.month+1)
    return start, end

def week_bounds(now=None, tz=UTC) -> tuple[datetime, datetime]:
    """Get start and end of current week"""
    now = now or datetime.now(tz)
    start = now - timedelta(days=7)
    return start, now

def _range_last_7_and_prev(now: datetime):
    """Get current and previous 7-day ranges"""
    cur_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
    cur_end = now
    prev_end = cur_start  # exclusive
    prev_start = (prev_end - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (cur_start, cur_end), (prev_start, prev_end)

def _range_this_month_and_prev(now: datetime):
    """Get current and previous month ranges"""
    cur_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cur_end = now
    prev_end = cur_start  # exclusive
    # find previous month start
    if cur_start.month == 1:
        prev_start = cur_start.replace(year=cur_start.year-1, month=12)
    else:
        prev_start = cur_start.replace(month=cur_start.month-1)
    return (cur_start, cur_end), (prev_start, prev_end)

def _totals_by_category(user_id: str, start: datetime, end: datetime):
    """Get category totals for a date range - UNIFIED READ PATH (expenses table only)"""
    from sqlalchemy import text

    from app import db
    
    # Use direct SQL query instead of prepared statement (fixed compatibility issue)
    try:
        result = db.session.execute(text("""
            SELECT 
                COALESCE(SUM(amount_minor), 0) as total_minor,
                COUNT(*) as expenses_count,
                (SELECT category FROM expenses 
                 WHERE user_id_hash = :user_hash AND created_at BETWEEN :start AND :end
                 GROUP BY category ORDER BY SUM(amount_minor) DESC NULLS LAST LIMIT 1) AS top_category
            FROM expenses 
            WHERE user_id_hash = :user_hash 
            AND created_at BETWEEN :start AND :end
        """), {"user_hash": user_id, "start": start, "end": end}).first()
        if result:
            total_minor = int(result[0] or 0)
            top_category = result[2] or "Uncategorized"
            # For compatibility, return category map with single entry
            category_map = {top_category: float(total_minor / 100)} if total_minor > 0 else {}
            total = float(total_minor / 100)
            return category_map, total
    except Exception:
        # Continue to fallback query if this fails
        pass
    
    # Fallback: Direct query only from expenses table (no other tables)
    rows = db.session.execute(text("""
        SELECT category, COALESCE(SUM(amount_minor), 0) as total_minor
        FROM expenses 
        WHERE user_id_hash = :user_id 
        AND created_at >= :start 
        AND created_at < :end
        GROUP BY category
    """), {"user_id": user_id, "start": start, "end": end}).fetchall()
    
    category_map = {(r[0] or "Uncategorized"): float((r[1] or 0) / 100) for r in rows}
    total = sum(category_map.values())
    return category_map, total

def _pct_change(cur: float, prev: float) -> float:
    """Calculate percentage change with divide-by-zero protection"""
    if prev == 0:
        return 100.0 if cur > 0 else 0.0
    return round(abs((cur - prev) / prev) * 100.0, 1)

def handle_summary(user_id: str, text: str = "", timeframe: str = "week") -> dict[str, str]:
    """
    Generate expense summary for user with intelligent timeframe detection
    Returns dict with 'text' key containing the summary message
    """
    try:
        from app import app, db
        
        # Ensure we're running within Flask application context
        with app.app_context():
            # Detect timeframe from user message if provided
            if text:
                text_lower = text.lower()
                if any(keyword in text_lower for keyword in ["month", "monthly", "this month", "months"]):
                    timeframe = "month"
                elif any(keyword in text_lower for keyword in ["week", "weekly", "last week", "this week"]):
                    timeframe = "week"
            
            # Get appropriate time bounds
            if timeframe == "month":
                start, end = month_bounds()
                period = "this month"
            else:
                start, end = week_bounds()
                period = "last 7 days"
            
            # Query expenses - UNIFIED READ PATH (expenses table only)
            from sqlalchemy import text
            expenses = db.session.execute(text("""
                SELECT category, COALESCE(SUM(amount_minor), 0) as total_minor, COUNT(*) as count
                FROM expenses 
                WHERE user_id_hash = :user_id 
                AND created_at >= :start 
                AND created_at < :end
                GROUP BY category
            """), {"user_id": user_id, "start": start, "end": end}).fetchall()
            
            # BLOCK 4 ANALYTICS: Track report request (fail-safe)
            try:
                from models import User
                from utils.analytics_engine import track_report_request
                user = db.session.query(User).filter_by(user_id_hash=user_id).first()
                if user:
                    track_report_request(user, "summary_command")
            except Exception as e:
                logger.debug(f"Report analytics tracking failed: {e}")
            
            # Generate AI summary reply
            from templates.replies_ai import format_ai_summary_reply, log_reply_banner
            log_reply_banner('SUMMARY', user_id)
            
            if not expenses:
                return {"text": format_ai_summary_reply(period, 0, 0, [])}
            
            # Calculate totals (from unified read path)
            total_amount = sum(float((exp[1] or 0) / 100) for exp in expenses)  # Convert minor to major units
            total_entries = sum(exp[2] for exp in expenses)
            
            # Build category list  
            categories = [exp[0] for exp in expenses[:5]]  # Top 5 categories
            
            # Generate base summary first
            base_msg = format_ai_summary_reply(period, total_amount, total_entries, categories)
            
            # Add budget comparison if possible
            from utils.ux_copy import (
                BUDGET_MONTH_COMPARISON,
                BUDGET_NO_DATA,
                BUDGET_TOP_CHANGE,
                BUDGET_WEEK_COMPARISON,
            )
            
            now = datetime.now(UTC)
            mode = "week" if timeframe == "week" else "month"
            
            try:
                # Get current and previous period ranges
                if mode == "week":
                    (cur_start, cur_end), (prev_start, prev_end) = _range_last_7_and_prev(now)
                else:
                    (cur_start, cur_end), (prev_start, prev_end) = _range_this_month_and_prev(now)
                
                # Get category totals for both periods
                cur_map, cur_total = _totals_by_category(user_id, cur_start, cur_end)
                prev_map, prev_total = _totals_by_category(user_id, prev_start, prev_end)
                
                if cur_total == 0 and prev_total == 0:
                    comparison_text = BUDGET_NO_DATA
                else:
                    # Find biggest mover by absolute delta among current categories
                    all_cats = set(cur_map) | set(prev_map)
                    if all_cats:
                        deltas = {c: cur_map.get(c, 0) - prev_map.get(c, 0) for c in all_cats}
                        top_cat = max(all_cats, key=lambda c: abs(deltas[c]))
                    else:
                        top_cat = "—"
                    
                    change_pct = _pct_change(cur_total, prev_total)
                    change_symbol = "⬆️" if (cur_total - prev_total) > 0 else "⬇️"
                    
                    if mode == "week":
                        comparison_text = BUDGET_WEEK_COMPARISON.format(change_symbol=change_symbol, pct=int(change_pct))
                    else:
                        comparison_text = BUDGET_MONTH_COMPARISON.format(change_symbol=change_symbol, pct=int(change_pct))
                    
                    comparison_text += BUDGET_TOP_CHANGE.format(category=top_cat)
                
                # Combine base summary with comparison, respecting 280 char limit
                candidate = f"{base_msg} {comparison_text}"
                msg = candidate if len(candidate) <= 280 else base_msg
                
            except Exception as e:
                logger.error(f"Error adding budget comparison: {e}")
                msg = base_msg  # Fail-quiet to base summary
            
            # PHASE F GROWTH TELEMETRY: Track report_requested event (fail-safe)
            try:
                from utils.telemetry import TelemetryTracker
                TelemetryTracker.track_report_requested(
                    user_id_hash=user_id,
                    report_type=f"summary_{timeframe}"
                )
            except Exception as e:
                # Fail-safe: telemetry errors never break report generation
                logger.debug(f"Report telemetry tracking failed: {e}")
            
            return {"text": msg}
        
    except Exception as e:
        logger.error(f"Summary handler error: {e}")
        return {"text": "Unable to generate summary. Please try again later."}