"""
FinBrain Router: Enhanced Money Detection and Intent Routing
Implements comprehensive contains_money() detector with multilingual support
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger("finbrain.router")

# Precompiled patterns for performance
CURRENCY_SYMBOL_PATTERN = re.compile(r'[৳$£€₹]\s*\d+(?:[.,]\d{1,2})?', re.IGNORECASE)
CURRENCY_WORD_PATTERN = re.compile(r'\b\d+(?:[.,]\d{1,2})?\s*(tk|taka|bdt|usd|eur|inr|rs|peso|php)\b|\b(tk|taka|bdt|usd|eur|inr|rs|peso|php)\s*\d+(?:[.,]\d{1,2})?\b', re.IGNORECASE)
VERB_PATTERN = re.compile(r'\b(spent|paid|bought|blew|burned|used)\b.*?\b\d+(?:[.,]\d{1,2})?\b', re.IGNORECASE)
SHORTHAND_PATTERN = re.compile(r'\b(coffee|lunch|dinner|uber|taxi|bus|groceries?|fuel|petrol|medicine|pharmacy)\b.*?\b\d+(?:[.,]\d{1,2})?\b', re.IGNORECASE)

# Bangla numeral mapping for normalization
BANGLA_NUMERALS = {
    '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
    '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
}

def normalize_text(text: str) -> str:
    """
    Normalize text for money detection.
    Converts Bangla numerals, handles OCR artifacts, removes extra spaces.
    """
    if not text:
        return ""
    
    # Convert Bangla numerals to ASCII
    normalized = text
    for bangla, ascii_num in BANGLA_NUMERALS.items():
        normalized = normalized.replace(bangla, ascii_num)
    
    # Collapse extra spaces and emojis
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s$£€₹৳.,()-]', ' ', normalized)  # Remove emojis, keep currency symbols
    
    return normalized.strip()

def contains_money(text: str) -> bool:
    """
    Enhanced money detection with comprehensive pattern matching.
    Ordered from cheapest to richest patterns, stops at first match.
    
    Args:
        text: Input text to analyze
        
    Returns:
        True if any money/expense patterns detected, False otherwise
    """
    if not text or not text.strip():
        return False
    
    # Normalize text for better pattern matching
    normalized_text = normalize_text(text)
    
    # Rule 1: Currency symbols with amounts (highest confidence)
    if CURRENCY_SYMBOL_PATTERN.search(normalized_text):
        return True
    
    # Rule 2: Amount with currency words
    if CURRENCY_WORD_PATTERN.search(normalized_text):
        return True
    
    # Rule 3: Action verbs with amounts
    if VERB_PATTERN.search(normalized_text):
        return True
    
    # Rule 4: Common expense shorthand with amounts
    if SHORTHAND_PATTERN.search(normalized_text):
        return True
    
    # Rule 5: Handle multipliers like "1.2k" or "1K"
    multiplier_pattern = re.compile(r'\b\d+(?:\.\d+)?[kK]\b.*?\b(tk|taka|spent|paid|bought|on|for)\b', re.IGNORECASE)
    if multiplier_pattern.search(normalized_text):
        return True
    
    return False

def test_contains_money():
    """Test cases for contains_money function"""
    test_cases = [
        # Should return True (money detected)
        ("Spent 100 on lunch", True),
        ("৳100 coffee", True),
        ("paid $25", True),
        ("bought €30 groceries", True),
        ("100 tk for transport", True),
        ("₹200 on dinner", True),
        ("spent 150.50 on shopping", True),
        ("£15.99 for books", True),
        
        # Should return False (no money detected)  
        ("summary", False),
        ("show me my expenses", False),
        ("hello", False),
        ("how are you", False),
        ("recap", False),
        ("", False),
        ("   ", False),
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = contains_money(text)
        if result != expected:
            print(f"FAIL: contains_money('{text}') = {result}, expected {expected}")
            all_passed = False
        else:
            print(f"PASS: contains_money('{text}') = {result}")
    
    return all_passed

if __name__ == "__main__":
    print("Testing contains_money() function:")
    test_contains_money()