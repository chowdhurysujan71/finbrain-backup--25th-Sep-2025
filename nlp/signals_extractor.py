"""
Deterministic bilingual signal extraction for EN/BN text
Handles time windows, money detection, and intent classification
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.text_normalizer import normalize_for_processing

# Create the nlp directory if it doesn't exist
import os
os.makedirs(os.path.dirname(__file__), exist_ok=True)

# Time window patterns (EN + BN)
RE_TIME = re.compile(r"\b(today|yesterday|this (week|month)|last (week|month))\b|\b\d{4}-\d{2}-\d{2}\b|আজ|গতকাল|এই (সপ্তাহ|মাস)|গত (সপ্তাহ|মাস)")

# Analysis patterns (explicit requests)
RE_ANALYSIS_EXPLICIT = re.compile(
    r"\b(analysis please|spending (summary|report)|what did i spend|expense report)\b|"
    r"analysis দাও|spending analysis|"
    r"বিশ্লেষণ( দাও)?|খরচের (সারাংশ|রিপোর্ট)|আমি কত খরচ করেছি"
)

# Analysis patterns (generic terms)
RE_ANALYSIS_GENERIC = re.compile(
    r"\b(analysis|summary|report)\b|বিশ্লেষণ|সারাংশ|রিপোর্ট"
)

# Coaching patterns
RE_COACHING = re.compile(
    r"\b(save|reduce|cut|budget|plan|help.*money|help.*spend)\b|"
    r"সেভ|কমানো|কাট|বাজেট|পরিকল্পনা|টাকা.*সাহায্য"
)

# FAQ patterns
RE_FAQ = re.compile(
    r"what can you do|how (do|does) it work|features?|capabilities?|"
    r"privacy|is my data (safe|private)|security|pricing|cost|subscription|plans?|"
    r"তুমি কী করতে পারো|কিভাবে কাজ করে|ফিচার|ক্ষমতা|প্রাইভেসি|"
    r"ডেটা নিরাপদ|নিরাপত্তা|দাম|মূল্য|সাবস্ক্রিপশন|প্ল্যান"
)

# Admin commands
RE_ADMIN = re.compile(r"^/(id|debug|help|status)\b")

# Money patterns (৳, tk, bdt, taka, টাকা) with ASCII numerals (Bengali converted by normalizer)
RE_MONEY = re.compile(
    r"(?:৳|tk|bdt|taka|টাকা)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)|"
    r"([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)\s*(?:৳|tk|bdt|taka|টাকা)"
)

def extract_signals(raw_text: str, user_id: str = None, timezone: str = "Asia/Dhaka") -> Dict:
    """
    Extract deterministic signals from text for routing decisions
    
    Args:
        raw_text: Original user input
        user_id: User identifier (unused in this implementation)
        timezone: Timezone for time window parsing
        
    Returns:
        Dictionary of extracted signals
    """
    # Normalize text for consistent pattern matching
    normalized = normalize_for_processing(raw_text)
    
    return {
        "is_admin": bool(RE_ADMIN.search(normalized)),
        "has_time_window": bool(RE_TIME.search(normalized)),
        "explicit_analysis_request": bool(RE_ANALYSIS_EXPLICIT.search(normalized)),
        "has_analysis_terms": bool(RE_ANALYSIS_GENERIC.search(normalized) or RE_ANALYSIS_EXPLICIT.search(normalized)),
        "has_coaching_verbs": bool(RE_COACHING.search(normalized)),
        "has_faq_terms": bool(RE_FAQ.search(normalized)),
        "money_mentions": [m.group(0) for m in RE_MONEY.finditer(normalized)],
        "has_money": bool(RE_MONEY.search(normalized)),
        "window": parse_time_window(timezone=timezone, text=normalized),
        "raw_text": raw_text,
        "normalized_text": normalized
    }

def parse_time_window(timezone: str, text: str) -> Optional[Dict]:
    """
    Parse time window references into date ranges
    
    Args:
        timezone: Target timezone (e.g., "Asia/Dhaka")
        text: Normalized text to parse
        
    Returns:
        Dictionary with 'from' and 'to' date strings, or None
    """
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(timezone)
    except ImportError:
        # Fallback for systems without zoneinfo
        from datetime import timezone as tz
        zone = tz.utc
    
    now = datetime.now(zone)
    today = now.date()
    
    # Today patterns
    if "today" in text or "আজ" in text:
        return {
            "from": str(today), 
            "to": str(today + timedelta(days=1)),
            "description": "today"
        }
    
    # Yesterday patterns
    if "yesterday" in text or "গতকাল" in text:
        yesterday = today - timedelta(days=1)
        return {
            "from": str(yesterday), 
            "to": str(today),
            "description": "yesterday"
        }
    
    # This week patterns
    if "this week" in text or "এই সপ্তাহ" in text:
        start = today - timedelta(days=today.weekday())  # Monday start
        return {
            "from": str(start), 
            "to": str(start + timedelta(days=7)),
            "description": "this week"
        }
    
    # Last week patterns
    if "last week" in text or "গত সপ্তাহ" in text:
        start = today - timedelta(days=today.weekday() + 7)
        return {
            "from": str(start), 
            "to": str(start + timedelta(days=7)),
            "description": "last week"
        }
    
    # This month patterns
    if "this month" in text or "এই মাস" in text:
        start = today.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1)
        else:
            end = start.replace(month=start.month + 1, day=1)
        return {
            "from": str(start), 
            "to": str(end),
            "description": "this month"
        }
    
    # Last month patterns
    if "last month" in text or "গত মাস" in text:
        if today.month == 1:
            start = today.replace(year=today.year - 1, month=12, day=1)
        else:
            start = today.replace(month=today.month - 1, day=1)
        end = today.replace(day=1)
        return {
            "from": str(start), 
            "to": str(end),
            "description": "last month"
        }
    
    # ISO date pattern (single day)
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso_match:
        try:
            date_obj = datetime.fromisoformat(iso_match.group(1)).date()
            return {
                "from": str(date_obj), 
                "to": str(date_obj + timedelta(days=1)),
                "description": f"date {iso_match.group(1)}"
            }
        except ValueError:
            pass
    
    return None