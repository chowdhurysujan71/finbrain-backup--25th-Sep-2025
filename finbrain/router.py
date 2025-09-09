"""
FinBrain Router: Enhanced Money Detection and Intent Routing
Implements comprehensive contains_money() detector with multilingual support

DEPRECATION WARNING: This module is deprecated. New code should use utils.production_router instead.
"""

import re
import logging
import warnings
from typing import Tuple, Optional

# Deprecation warning for this module
warnings.warn(
    "finbrain.router is deprecated. Use utils.production_router for new code. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

logger = logging.getLogger("finbrain.deprecated_router")
logger.warning("Deprecated finbrain.router module imported. Consider migrating to utils.production_router.")

# Correction message patterns - compiled for performance
CORRECTION_PATTERNS = re.compile(
    r'\b(?:sorry|i meant|meant|actually|replace last|correct that|correction|should be|update to|make it|not\s+\d+|typo)\b',
    re.IGNORECASE
)

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

def is_correction_message(text: str) -> bool:
    """
    Detect correction messages using pattern matching.
    
    Args:
        text: Input text to check for correction patterns
        
    Returns:
        True if text contains correction patterns, False otherwise
    """
    if not text or not text.strip():
        return False
    
    # Check for correction patterns
    return bool(CORRECTION_PATTERNS.search(text.lower()))

def contains_money_with_correction_fallback(text: str, psid_hash: str) -> bool:
    """
    Enhanced money detection that includes correction-specific fallbacks.
    Only applies fallback when SMART_CORRECTIONS is enabled and message is a correction.
    
    Args:
        text: Input text to analyze
        psid_hash: User's PSID hash for feature flag check
        
    Returns:
        True if money detected (including correction fallbacks), False otherwise
    """
    # First try standard money detection
    if contains_money(text):
        return True
    
    # If standard detection failed, check if this is a correction message with fallback enabled
    from utils.feature_flags import feature_enabled
    
    if not feature_enabled(psid_hash, "SMART_CORRECTIONS"):
        return False
        
    if not is_correction_message(text):
        return False
    
    # Correction-specific fallback patterns (only for correction messages)
    normalized_text = normalize_text(text)
    
    # Pattern 1: Bare numbers (2-7 digits) with optional decimals
    bare_number_pattern = re.compile(r'\b\d{1,7}(?:[.,]\d{1,2})?\b')
    if bare_number_pattern.search(normalized_text):
        logger.debug(f"Correction fallback: bare number detected in '{text[:50]}...'")
        return True
    
    # Pattern 2: k shorthand (1.2k, 500k, etc.)
    k_shorthand_pattern = re.compile(r'\b\d+(?:\.\d+)?k\b', re.IGNORECASE)
    if k_shorthand_pattern.search(normalized_text):
        logger.debug(f"Correction fallback: k shorthand detected in '{text[:50]}...'")
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