# parser.py - Hardened expense message parser
import re

BN_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
CURRENCY = r"[৳$€£₹]"

AMOUNT = r"(?P<amt>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)"
NOTE   = r"(?P<note>.+?)"

LOG_PATTERNS = [
    rf"^(?:log|spent|add)\s+{CURRENCY}?\s*{AMOUNT}\s+{NOTE}$",   # log 250 lunch / log ৳250 lunch
    rf"^{CURRENCY}?\s*{AMOUNT}\s+{NOTE}$",                      # 250 lunch / ৳250 lunch
    rf"^{NOTE}\s+{CURRENCY}?\s*{AMOUNT}$",                      # lunch 250 / lunch ৳250
]

ZERO_WIDTH = r"[\u200B-\u200D\u2060]"

def _clean_text(s: str) -> str:
    """Clean text by removing zero-width chars and normalizing whitespace"""
    s = (s or "").translate(BN_MAP)
    s = re.sub(ZERO_WIDTH, "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _clean_amount(s: str) -> float:
    """Extract and clean amount from string"""
    s = re.sub(CURRENCY, "", s)
    s = s.replace(",", "")
    return round(float(s), 2)

def parse_expense(msg: str):
    """
    Parse expense message and return (amount, description) tuple.
    Returns None if no valid expense pattern is found.
    
    Supported formats:
    - log 250 lunch
    - spent 120 taxi gulshan
    - ৳300 groceries
    - 300 groceries
    - groceries 300
    - ডিনার ৪৫০
    - add $12.50 snacks
    """
    t = _clean_text(msg)
    for pat in LOG_PATTERNS:
        m = re.match(pat, t, flags=re.IGNORECASE)
        if not m: 
            continue
        amt_str = m.group("amt")
        note = m.group("note").strip(" .-—_/\\|")
        
        # Guard: if note accidentally starts with a lone decimal fragment like ".0"
        note = re.sub(r"^\.(?:0|00)\b\s*", "", note)  # kills ".0 " prefix safely
        
        if not note:
            note = "misc"
            
        return _clean_amount(amt_str), note
        
    return None  # no match