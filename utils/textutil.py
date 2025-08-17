"""
Last-mile text utilities for safe formatting, sanitization, and variants
Handles EMOJI_ENABLED, SAY_ENABLED, MAX_REPLY_LEN flags for production control
"""
import os
import re
import random
import logging
from typing import Union, Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Configuration from environment (safe defaults)
SAY_ENABLED = os.environ.get("SAY_ENABLED", "true").lower() == "true"
EMOJI_ENABLED = os.environ.get("EMOJI_ENABLED", "true").lower() == "true"
MAX_REPLY_LEN = int(os.environ.get("MAX_REPLY_LEN", "280"))
PANIC_PLAIN_REPLY = os.environ.get("PANIC_PLAIN_REPLY", "false").lower() == "true"

# Variant banks for dynamic responses
LOGGED_VARIANTS = [
    "✅ Got it — ৳{amount} for {note} ({category}).",
    "Logged: ৳{amount} — {note}. Nice.",
    "All set. ৳{amount} to {category} for {note}."
]

SUMMARY_VARIANTS = [
    "📊 Last 7 days: ৳{total}\n🍔 {food} • 🚗 {ride} • 🧾 {bill} • 🛒 {grocery} • 🧩 {other}\n💡 {tip}",
    "Here's your week: ৳{total}\nFood {food}, Ride {ride}, Bills {bill}, Grocery {grocery}, Other {other}\n💡 {tip}",
    "Weekly spend ৳{total}. Food {food} | Ride {ride} | Bills {bill} | Grocery {grocery} | Other {other}\n💡 {tip}"
]

HELP_VARIANTS = [
    "Try log 50 coffee. For totals, type summary.",
    "Log with: log [amount] [note]. Weekly view: summary.",
    "Need a hand? log 120 lunch or summary for a quick recap."
]

# RL-2 ASCII-safe variants (no emojis, safe for rate limiting)
RL2_DISCLAIMER = "NOTE: Taking a quick breather. I can do 4 smart replies per minute per person.\nOK: I handled that without AI this time.\nTip: type \"summary\" for a quick recap."

RL2_BREATHER_SUMMARY_PREFIX = "NOTE: Smart replies are capped at 4/min. Here is your recap without AI:"

def safe_format(template: str, data: Dict[str, Any]) -> str:
    """
    Safe string formatting that leaves {missing} keys as-is (no exceptions)
    """
    try:
        # Replace known keys, leave unknown ones intact
        result = template
        for key, value in data.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    except Exception as e:
        logger.warning(f"Safe format error: {e}")
        return template

def normalize(message: str) -> str:
    """
    Normalize message: replace CR/TAB/NEWLINE with spaces, strip zero-width chars,
    collapse whitespace, optionally remove emojis if EMOJI_ENABLED=false
    """
    if not message:
        return ""
    
    # Replace control chars with spaces
    normalized = re.sub(r'[\r\t\n]+', ' ', message)
    
    # Remove zero-width characters
    normalized = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', normalized)
    
    # Remove other problematic Unicode control characters
    normalized = ''.join(char for char in normalized if ord(char) >= 32 or char.isspace())
    
    # Collapse whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Remove emojis if disabled
    if not EMOJI_ENABLED:
        # Remove emoji characters (basic emoji ranges)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        normalized = emoji_pattern.sub('', normalized)
        
        # Remove other common emoji-like characters
        normalized = normalized.replace('✅', '').replace('📊', '').replace('💡', '')
        normalized = normalized.replace('🍔', '').replace('🚗', '').replace('🧾', '')
        normalized = normalized.replace('🛒', '').replace('🧩', '').replace('↩️', '')
        
        # Clean up any double spaces from emoji removal
        normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def cap_len(message: str, max_len: Optional[int] = None) -> str:
    """Hard cap message length"""
    if max_len is None:
        max_len = MAX_REPLY_LEN
    
    if len(message) <= max_len:
        return message
    
    # Truncate with ellipsis
    return message[:max_len-3] + "..."

def finalize_message(template_or_list: Union[str, List[str]], data: Optional[Dict[str, Any]] = None) -> str:
    """
    Complete message processing pipeline:
    1. Pick variant if SAY_ENABLED=true and list provided
    2. Safe format with data
    3. Normalize (control chars, emojis, etc.)
    4. Cap length
    5. Never returns None (fallback to "OK")
    """
    if data is None:
        data = {}
    
    # Panic mode - return simple acknowledgment
    if PANIC_PLAIN_REPLY:
        return "OK"
    
    try:
        # Step 1: Select template
        if isinstance(template_or_list, list):
            if SAY_ENABLED and template_or_list:
                template = random.choice(template_or_list)
            else:
                # Use first variant when SAY_ENABLED=false
                template = template_or_list[0] if template_or_list else "OK"
        else:
            template = template_or_list or "OK"
        
        # Step 2: Safe format
        formatted = safe_format(template, data)
        
        # Step 3: Normalize
        normalized = normalize(formatted)
        
        # Step 4: Cap length
        capped = cap_len(normalized)
        
        # Step 5: Ensure never empty
        return capped if capped.strip() else "OK"
        
    except Exception as e:
        logger.error(f"Message finalization error: {e}")
        return "OK"

def say(options: Union[str, List[str]], data: Optional[Dict[str, Any]] = None) -> str:
    """
    Wrapper over finalize_message for convenient variant handling
    """
    return finalize_message(options, data)

def get_rl2_disclaimer() -> str:
    """Get RL-2 disclaimer (always ASCII-safe)"""
    return normalize(RL2_DISCLAIMER)

def get_rl2_summary_prefix() -> str:
    """Get RL-2 summary prefix (always ASCII-safe)"""
    return normalize(RL2_BREATHER_SUMMARY_PREFIX)

def format_logged_response(amount: float, note: str, category: str) -> str:
    """Format expense logged response with variants"""
    data = {
        'amount': f"{amount:.2f}",
        'note': note,
        'category': category
    }
    return say(LOGGED_VARIANTS, data)

def format_summary_response(totals: Dict[str, float], tip: Optional[str] = None) -> str:
    """Format summary response with variants"""
    data = {
        'total': f"{totals.get('total', 0):.0f}",
        'food': f"{totals.get('food', 0):.0f}",
        'ride': f"{totals.get('ride', 0):.0f}",
        'bill': f"{totals.get('bill', 0):.0f}",
        'grocery': f"{totals.get('grocery', 0):.0f}",
        'other': f"{totals.get('other', 0):.0f}",
        'tip': tip or "Keep tracking for better insights!"
    }
    
    # Try full summary, fall back to shorter versions if over limit
    full_response = say(SUMMARY_VARIANTS, data)
    
    if len(full_response) > MAX_REPLY_LEN:
        # Remove tip and try again
        data['tip'] = ""
        shorter_response = say(SUMMARY_VARIANTS, data)
        if len(shorter_response) > MAX_REPLY_LEN:
            # Emergency fallback
            return f"Weekly total: ৳{data['total']}"
        return shorter_response
    
    return full_response

def format_help_response() -> str:
    """Format help response with variants"""
    return say(HELP_VARIANTS)

def format_undo_response(amount: Optional[float] = None, note: Optional[str] = None) -> str:
    """Format undo response"""
    if amount is not None and note is not None:
        if EMOJI_ENABLED:
            return f"↩️ Removed ৳{amount:.2f} — {note}."
        else:
            return f"Removed ৳{amount:.2f} — {note}."
    else:
        return "Nothing to undo yet."

# Static tip bank for AI-enhanced summaries
DEFAULT_TIPS = [
    "Try categorizing by location to spot patterns!",
    "Set a weekly budget to stay on track.",
    "Review your biggest category each week.",
    "Small daily expenses add up quickly.",
    "Track both wants and needs separately."
]

def get_random_tip() -> str:
    """Get a random tip from the tip bank"""
    return random.choice(DEFAULT_TIPS)