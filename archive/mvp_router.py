"""MVP Router with regex-based intent matching and lightweight processing"""
import re
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

from utils.user_manager import resolve_user_id

logger = logging.getLogger(__name__)

# Regex patterns for intent matching
LOG_PATTERN = re.compile(r'^log (\d+) (.*)$', re.IGNORECASE)
SUMMARY_PATTERN = re.compile(r'^summary$', re.IGNORECASE)

# Simple keyword categories for summary
CATEGORY_KEYWORDS = {
    'food': ['food', 'eat', 'lunch', 'dinner', 'breakfast', 'meal', 'restaurant', 'cafe', 'coffee'],
    'ride': ['uber', 'taxi', 'ride', 'bus', 'transport', 'rickshaw', 'cng'],
    'bill': ['bill', 'electricity', 'internet', 'phone', 'utility', 'rent'],
    'grocery': ['grocery', 'market', 'shop', 'shopping', 'store', 'supermarket'],
    'other': []  # catch-all
}

def hash_psid(psid: str) -> str:
    """Generate SHA-256 hash of PSID for logging (no PII)"""
    return hashlib.sha256(psid.encode()).hexdigest()[:16]

def categorize_expense(note: str) -> str:
    """Simple keyword-based categorization"""
    note_lower = note.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == 'other':
            continue
        for keyword in keywords:
            if keyword in note_lower:
                return category
    return 'other'

def process_log_intent(psid: str, amount_str: str, note: str) -> str:
    """Process expense logging intent"""
    try:
        # Import here to avoid circular import
        from models import Expense, User, db
        
        amount = float(amount_str)
        category = categorize_expense(note)
        
        # Create expense record
        expense = Expense(
            user_id=resolve_user_id(psid=psid),
            description=note[:100],  # Truncate for DB
            amount=amount,
            category=category,
            currency='৳',
            month=datetime.now().strftime('%Y-%m'),
            unique_id=f"mvp_{psid}_{int(datetime.now().timestamp())}",
            platform='messenger',
            original_message=f"log {amount_str} {note}"
        )
        
        # Update or create user record with 24-hour policy tracking
        user_hash = resolve_user_id(psid=psid)
        user = User.query.filter_by(user_id_hash=user_hash).first()
        if not user:
            user = User(
                user_id_hash=user_hash,
                platform='messenger',
                last_user_message_at=datetime.utcnow()
            )
            db.session.add(user)
        else:
            user.last_user_message_at = datetime.utcnow()
        
        user.total_expenses = (user.total_expenses or 0) + amount
        user.expense_count = (user.expense_count or 0) + 1
        user.last_interaction = datetime.utcnow()
        
        # Save to database
        db.session.add(expense)
        db.session.commit()
        
        # Format response (≤ 280 chars)
        response = f"Logged: ৳{amount_str} — {note}"
        if len(response) > 280:
            truncated_note = note[:270 - len(f"Logged: ৳{amount_str} — ")]
            response = f"Logged: ৳{amount_str} — {truncated_note}..."
            
        return response
        
    except ValueError:
        return "Invalid amount. Use: log 100 description"
    except Exception as e:
        logger.error(f"Error processing log intent: {str(e)}")
        return "Sorry, couldn't log expense. Please try again."

def process_summary_intent(psid: str) -> str:
    """Process summary intent - last 7 days by category"""
    try:
        # Import here to avoid circular import
        from models import Expense
        
        user_hash = resolve_user_id(psid=psid)
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # Get expenses from last 7 days
        expenses = Expense.query.filter(
            Expense.user_id == user_hash,
            Expense.created_at >= seven_days_ago
        ).all()
        
        if not expenses:
            return "No expenses logged in the last 7 days. Start with: log 100 lunch"
        
        # Calculate totals by category
        category_totals = {}
        total_amount = 0
        
        for expense in expenses:
            category = expense.category
            amount = float(expense.amount)
            category_totals[category] = category_totals.get(category, 0) + amount
            total_amount += amount
        
        # Format summary (≤ 280 chars)
        lines = [f"7-day total: ৳{total_amount:.0f}"]
        
        # Add top categories
        sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        for category, amount in sorted_categories[:2]:  # Top 2 categories
            lines.append(f"{category.title()}: ৳{amount:.0f}")
        
        # Add actionable tip
        lines.append("💡 Track small expenses to see spending patterns")
        
        response = " | ".join(lines)
        if len(response) > 280:
            response = response[:277] + "..."
            
        return response
        
    except Exception as e:
        logger.error(f"Error processing summary intent: {str(e)}")
        return "Sorry, couldn't generate summary. Please try again."

def get_help_message() -> str:
    """Return help message with examples"""
    return """FinBrain Help:
• log 250 lunch at restaurant
• summary
Type 'summary' anytime for a quick recap.
Send any expense message to get started!"""

def route_message(psid: str, message_text: str) -> Tuple[str, str]:
    """Route message based on regex patterns
    
    Returns: (response_text, intent_matched)
    """
    message_text = message_text.strip()
    
    # Check for log intent
    log_match = LOG_PATTERN.match(message_text)
    if log_match:
        amount_str = log_match.group(1)
        note = log_match.group(2).strip()
        response = process_log_intent(psid, amount_str, note)
        return response, "log"
    
    # Check for summary intent
    if SUMMARY_PATTERN.match(message_text):
        response = process_summary_intent(psid)
        return response, "summary"
    
    # Default to help
    response = get_help_message()
    return response, "help"

def log_structured_event(rid: str, psid: str, mid: str, route: str, duration_ms: float, outcome: str, intent: str = None):
    """Log structured JSON event (no PII)"""
    log_data = {
        "rid": rid,
        "psid_hash": resolve_user_id(psid=psid),
        "mid": mid,
        "route": route,
        "duration_ms": round(duration_ms, 1),
        "outcome": outcome
    }
    
    if intent:
        log_data["intent"] = intent
        
    logger.info(json.dumps(log_data, separators=(',', ':')))