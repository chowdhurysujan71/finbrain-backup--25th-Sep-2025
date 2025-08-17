"""
Enhanced UX components for FinBrain with structured messaging, retention loops, and response formatting
Implements the user experience specifications including fallback messaging, system prompts, and quick replies
"""

import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from collections import Counter
from config import MSG_MAX_CHARS

logger = logging.getLogger(__name__)

# Observability counters (per minute)
metrics = Counter()

def record_event(name: str, n: int = 1):
    """Record UX events for observability"""
    metrics[name] += n

def telemetry_snapshot() -> Dict[str, Any]:
    """Return observability metrics snapshot"""
    return {
        "counters": dict(metrics),
        "avg_chars_per_msg": round(
            metrics.get("total_chars", 0) / max(1, metrics.get("messages_sent", 0)), 1
        ),
    }

# System prompt for AI coach with 2-3 sentence limit and action-oriented responses
SYSTEM_PROMPT = """
You are a personable financial coach.
Reply in 2–3 sentences max. Ask one crisp follow-up if needed.
Prefer actions over essays. Offer a next step (button-like suggestion).
Avoid jargon. Use numbers when helpful.
"""

def format_coach_reply(summary: str, action: str, question: str) -> str:
    """Format AI coach reply with 280-char cap and graceful clipping"""
    text = f"{summary}\n{action}\n{question}"
    if len(text) <= MSG_MAX_CHARS:
        return text
    # Hard cap with a graceful "show more" hook
    clipped = text[:MSG_MAX_CHARS-18].rstrip()
    return f"{clipped}… Want details?"

def safe_send_text(send_func, psid: str, text: str):
    """Send text with automatic 280-char limit enforcement"""
    record_event("messages_sent")
    record_event("total_chars", len(text))
    
    if len(text) <= MSG_MAX_CHARS:
        return send_func(psid, text)
    
    clipped = f"{text[:MSG_MAX_CHARS-18].rstrip()}… Want details?"
    send_func(psid, clipped)
    # Note: Quick replies for "Show more" would be handled by caller
    record_event("messages_clipped")

# Fast non-AI utilities (work during cool-downs)
def parse_expense(text: str) -> Tuple[Optional[str], Optional[float]]:
    """Parse expense from text like 'Groceries 650' or '650 groceries'"""
    # Pattern: category amount or amount category
    patterns = [
        r"\s*([A-Za-z ]+)\s+(\d+(?:\.\d{1,2})?)\s*$",  # "Groceries 650"
        r"\s*(\d+(?:\.\d{1,2})?)\s+([A-Za-z ]+)\s*$",  # "650 groceries"
    ]
    
    for i, pattern in enumerate(patterns):
        m = re.match(pattern, text)
        if m:
            if i == 0:  # category first
                return (m.group(1).strip().title(), float(m.group(2)))
            else:  # amount first
                return (m.group(2).strip().title(), float(m.group(1)))
    
    return (None, None)

def snapshot_last_7_days(db_func, psid: str) -> str:
    """Generate 7-day spending snapshot by category"""
    try:
        rows = db_func(psid, days=7)  # Expected: [(category, amount_float)]
        if not rows:
            return "No spend logged in the last 7 days."
        
        top = sorted(rows, key=lambda x: x[1], reverse=True)[:3]
        summary = ", ".join([f"{c} ৳{int(a):,}" for c, a in top])
        return f"7-day snapshot: {summary}."
    except Exception as e:
        logger.error(f"Snapshot generation failed: {e}")
        return "Unable to generate snapshot right now."

def check_caps_and_alert(db_func, send_func, psid: str):
    """Check budget caps and send alerts if over limit"""
    try:
        alerts = []
        caps = db_func("get_caps", psid)  # Expected: [{"category": str, "limit_bdt": float}]
        
        for cap in caps:
            spent = db_func("get_spend", psid, category=cap["category"], month="current")
            if spent > cap["limit_bdt"]:
                over = int(spent - cap["limit_bdt"])
                alerts.append((cap["category"], over))
        
        for cat, over in alerts:
            message = (
                f"Your {cat} is over budget by ৳{over:,}. "
                f"Want me to lower next month's cap or show where it's going?"
            )
            safe_send_text(send_func, psid, message)
            record_event(f"budget_alert:{cat}")
            
    except Exception as e:
        logger.error(f"Budget cap check failed: {e}")

# Message sequencing helpers (structured quick replies)
def send_hook(send_func, psid: str, amount_bdt: int, delta_pct: int):
    """Send spending trend hook message"""
    message = f"You spent ৳{amount_bdt:,} on dining this week—{delta_pct:+d}% vs last week."
    safe_send_text(send_func, psid, message)
    record_event("hook_sent:dining_trend")

def send_action(send_func, quick_reply_func, psid: str, next_cap_bdt: int):
    """Send action message with structured quick replies"""
    message = f"Want me to set a ৳{next_cap_bdt:,} cap for next week?"
    safe_send_text(send_func, psid, message)
    
    quick_reply_func(psid, [
        {"title": "Yes, set cap", "payload": "SET_DINING_CAP_YES"},
        {"title": "Show breakdown", "payload": "SHOW_DINING_BREAKDOWN"},
        {"title": "Not now", "payload": "IGNORE_DINING_CAP"},
    ])
    record_event("action_sent:set_cap")

def send_picker(send_func, quick_reply_func, psid: str, prompt: str = "Pick one:"):
    """Send generic quick-reply picker"""
    safe_send_text(send_func, psid, prompt)
    
    quick_reply_func(psid, [
        {"title": "Log Expense", "payload": "LOG_EXPENSE"},
        {"title": "Weekly Review", "payload": "WEEKLY_REVIEW"},
        {"title": "Set Goal", "payload": "SET_GOAL"},
    ])
    record_event("picker_sent")

# Advisor loops (retention)
def loop_daily_checkin(send_func, quick_reply_func, psid: str):
    """Daily micro check-in for user engagement"""
    message = "Good evening! Any expenses to log today, or check your balance?"
    safe_send_text(send_func, psid, message)
    
    quick_reply_func(psid, [
        {"title": "Log", "payload": "LOG_EXPENSE"},
        {"title": "Balance", "payload": "SHOW_BALANCE"},
        {"title": "Skip", "payload": "SKIP_TODAY"},
    ])
    record_event("daily_checkin_sent")

def loop_weekly_review(send_func, quick_reply_func, psid: str, 
                      groceries_bdt: int, groceries_delta_pct: int, 
                      dining_bdt: int, dining_delta_pct: int):
    """Weekly review with automatic summary and target setting"""
    summary = (
        f"Week review: Groceries ৳{groceries_bdt:,} ({groceries_delta_pct:+d}%), "
        f"Dining ৳{dining_bdt:,} ({dining_delta_pct:+d}%)."
    )
    safe_send_text(send_func, psid, summary)
    
    target_message = "Target for next week: Dining ≤ ৳6,500?"
    safe_send_text(send_func, psid, target_message)
    
    quick_reply_func(psid, [
        {"title": "Set Target", "payload": "SET_TARGET_DINING_6500"},
        {"title": "See Chart", "payload": "SEE_WEEKLY_CHART"},
        {"title": "Ignore", "payload": "IGNORE_WEEKLY_TARGET"},
    ])
    record_event("weekly_review_sent")

def loop_goal_tracker(send_func, quick_reply_func, psid: str, 
                     current_bdt: int, target_bdt: int, suggested_add_bdt: int = 5000):
    """Goal tracking with progress and suggested actions"""
    pct = round(100 * (current_bdt / max(1, target_bdt)))
    message = (
        f"Emergency fund: ৳{current_bdt:,}/৳{target_bdt:,} ({pct}%). "
        f"Add ৳{suggested_add_bdt:,} this week?"
    )
    safe_send_text(send_func, psid, message)
    
    quick_reply_func(psid, [
        {"title": f"Add ৳{suggested_add_bdt:,}", "payload": f"GOAL_ADD_{suggested_add_bdt}"},
        {"title": "Change Goal", "payload": "GOAL_CHANGE"},
        {"title": "Not now", "payload": "GOAL_LATER"},
    ])
    record_event("goal_tracker_sent")

def loop_smart_nudge(send_func, quick_reply_func, psid: str, 
                    category: str, delta_pct: int, proposed_cap_bdt: int):
    """Smart nudges for spending alerts"""
    message = (
        f"Heads-up: your {category} is trending {delta_pct:+d}% this month. "
        f"Cap it at ৳{proposed_cap_bdt:,}?"
    )
    safe_send_text(send_func, psid, message)
    
    details_label = "See trips" if category == "ride-hailing" else "See details"
    quick_reply_func(psid, [
        {"title": "Cap", "payload": f"CAP_{category.upper()}_{proposed_cap_bdt}"},
        {"title": details_label, "payload": f"DETAILS_{category.upper()}"},
        {"title": "Dismiss", "payload": f"DISMISS_{category.upper()}"},
    ])
    record_event(f"smart_nudge_sent:{category}")

# Payload handlers for quick replies
def handle_payload(psid: str, payload: str, db_func, send_func, quick_reply_func) -> bool:
    """Handle quick reply payloads. Returns True if handled, False if not recognized"""
    
    try:
        if payload == "SHOW_SNAPSHOT":
            snapshot = snapshot_last_7_days(db_func, psid)
            safe_send_text(send_func, psid, snapshot)
            send_picker(send_func, quick_reply_func, psid)
            record_event("payload_handled:snapshot")
            return True
            
        elif payload == "SET_GOAL":
            safe_send_text(send_func, psid, "Which category should we cap?")
            record_event("payload_handled:set_goal")
            return True
            
        elif payload == "SET_DINING_CAP_YES":
            db_func("set_cap", psid, "Dining", 6500)
            safe_send_text(send_func, psid, "Done. Dining cap set to ৳6,500 for next week.")
            record_event("payload_handled:dining_cap")
            return True
            
        elif payload.startswith("GOAL_ADD_"):
            amt = int(payload.split("_")[-1])
            db_func("transfer_to_goal", psid, amt)
            safe_send_text(send_func, psid, f"Added ৳{amt:,} to your goal.")
            record_event("payload_handled:goal_add")
            return True
            
        elif payload == "LOG_EXPENSE":
            safe_send_text(send_func, psid, "Type your expense like 'Lunch 250' or '250 lunch'")
            record_event("payload_handled:log_prompt")
            return True
            
        elif payload == "WEEKLY_REVIEW":
            # This would trigger a weekly review - placeholder for now
            safe_send_text(send_func, psid, "Generating your weekly review...")
            record_event("payload_handled:weekly_review")
            return True
            
        elif payload in ["SKIP_TODAY", "IGNORE_DINING_CAP", "IGNORE_WEEKLY_TARGET", "GOAL_LATER"]:
            safe_send_text(send_func, psid, "No problem! I'm here when you need me.")
            record_event(f"payload_handled:{payload.lower()}")
            return True
            
        else:
            record_event("payload_unhandled")
            return False
            
    except Exception as e:
        logger.error(f"Payload handling error for {payload}: {e}")
        record_event("payload_error")
        return False

# Main message handler integrating all components
def handle_enhanced_message(psid: str, text: str, db_func, send_func, quick_reply_func, 
                          ai_func, rate_limiter_func) -> bool:
    """
    Enhanced message handler with UX components
    Returns True if message was handled, False if needs fallback
    """
    
    # Quick intent switches for non-AI utilities
    cat, amt = parse_expense(text)
    if cat and amt:
        try:
            db_func("add_expense", psid, category=cat, amount=amt)
            safe_send_text(send_func, psid, f"Logged {cat} ৳{int(amt):,}. Need a 7-day snapshot?")
            
            quick_reply_func(psid, [
                {"title": "Yes, snapshot", "payload": "SHOW_SNAPSHOT"},
                {"title": "Set a cap", "payload": "SET_GOAL"},
                {"title": "Done", "payload": "DONE"},
            ])
            record_event("expense_logged")
            return True
            
        except Exception as e:
            logger.error(f"Expense logging failed: {e}")
            safe_send_text(send_func, psid, "Unable to log expense right now. Please try again.")
            return True

    # AI path (assumes rate limiting already applied)
    allowed, retry_in = rate_limiter_func(psid)
    if not allowed:
        # Use the exact fallback copy specified
        fallback_message = (
            f"Taking a quick breather to stay fast & free. "
            f"I'll do the smart analysis in ~{retry_in}s. Meanwhile, want a quick action?"
        )
        safe_send_text(send_func, psid, fallback_message)
        send_picker(send_func, quick_reply_func, psid)
        record_event("fallback_sent")
        return True

    # Build short-burst reply from AI signal
    try:
        insight = ai_func(psid, text, system_prompt=SYSTEM_PROMPT)
        
        # Example mapping insight → rubric fields:
        summary = insight.get("summary", "Here's a quick take.")
        action = insight.get("action", "Want me to set a simple budget so this stays on track?")
        question = insight.get("question", "See details or set a cap?")

        formatted_reply = format_coach_reply(summary, action, question)
        safe_send_text(send_func, psid, formatted_reply)
        
        quick_reply_func(psid, [
            {"title": "Show breakdown", "payload": "SHOW_BREAKDOWN"},
            {"title": "Set a cap", "payload": "SET_GOAL"},
            {"title": "Not now", "payload": "IGNORE"},
        ])
        record_event("ai_allowed")
        return True
        
    except Exception as e:
        logger.error(f"AI processing failed: {e}")
        safe_send_text(send_func, psid, "I'm having trouble processing that. Can you try rephrasing?")
        record_event("ai_error")
        return True

def get_ux_metrics() -> Dict[str, Any]:
    """Get UX metrics for observability endpoint"""
    return {
        "ux_metrics": telemetry_snapshot(),
        "top_payloads": dict(Counter({k: v for k, v in metrics.items() if k.startswith("payload_handled:")}).most_common(5)),
        "engagement_rate": round(
            metrics.get("payload_handled:log_prompt", 0) / max(1, metrics.get("picker_sent", 0)) * 100, 1
        )
    }