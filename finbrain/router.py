"""
FinBrain Router: Money Detection and Intent Routing
Implements contains_money() detector that prioritizes LOG over SUMMARY
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger("finbrain.router")

def contains_money(text: str) -> bool:
    """
    Detect if text contains money/expense indicators.
    Returns True if any money patterns are found, ensuring LOG intent over SUMMARY.
    """
    if not text or not text.strip():
        return False
    
    text_clean = text.strip()
    
    # Pattern 1: Currency symbols with amounts
    # r'(?i)[৳$£€₹]\s*\d+(?:\.\d{1,2})?'
    currency_pattern = re.compile(r'(?i)[৳$£€₹]\s*\d+(?:\.\d{1,2})?')
    if currency_pattern.search(text_clean):
        return True
    
    # Pattern 2: Spent/paid/bought keywords with amounts
    # r'(?i)\b(spent|paid|bought)\b.*?(\d+(?:\.\d{1,2})?)'
    action_pattern = re.compile(r'(?i)\b(spent|paid|bought)\b.*?(\d+(?:\.\d{1,2})?)')
    if action_pattern.search(text_clean):
        return True
    
    # Pattern 3: Amount + "on/for" prepositions
    # r'(?i)\b(?:tk|৳|bdt|usd|eur|inr|rs|rs\.)?\s*(\d+(?:\.\d{1,2})?)\b.*?\b(on|for)\b'
    preposition_pattern = re.compile(r'(?i)\b(?:tk|৳|bdt|usd|eur|inr|rs|rs\.)?\s*(\d+(?:\.\d{1,2})?)\b.*?\b(on|for)\b')
    if preposition_pattern.search(text_clean):
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