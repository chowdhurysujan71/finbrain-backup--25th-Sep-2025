"""
Unified Expense Parser: Shared by STD and AI modes
Extracts amount, currency, category, and note from text
"""

import re
from decimal import Decimal
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("parsers.expense")

# Currency symbol mapping
CURRENCY_SYMBOLS = {
    '৳': 'BDT',
    '$': 'USD', 
    '£': 'GBP',
    '€': 'EUR',
    '₹': 'INR'
}

# Currency word mapping
CURRENCY_WORDS = {
    'tk': 'BDT',
    '৳': 'BDT', 
    'bdt': 'BDT',
    'usd': 'USD',
    'eur': 'EUR', 
    'inr': 'INR',
    'rs': 'INR',
    'rs.': 'INR'
}

# Category aliases for normalization
CATEGORY_ALIASES = {
    # Food & Dining
    'food': 'food',
    'lunch': 'food',
    'dinner': 'food', 
    'breakfast': 'food',
    'meal': 'food',
    'snack': 'food',
    'coffee': 'food',
    'tea': 'food',
    'restaurant': 'food',
    'cafe': 'food',
    
    # Transport
    'transport': 'transport',
    'uber': 'transport',
    'taxi': 'transport',
    'bus': 'transport', 
    'train': 'transport',
    'ride': 'transport',
    'gas': 'transport',
    'fuel': 'transport',
    
    # Shopping
    'shopping': 'shopping',
    'clothes': 'shopping',
    'shirt': 'shopping',
    'dress': 'shopping',
    'shoes': 'shopping',
    
    # Groceries
    'groceries': 'groceries',
    'grocery': 'groceries',
    'market': 'groceries',
    'vegetables': 'groceries',
    'fruits': 'groceries',
    
    # Entertainment
    'entertainment': 'entertainment',
    'movie': 'entertainment',
    'cinema': 'entertainment',
    'game': 'entertainment',
    
    # Health
    'health': 'health',
    'medicine': 'health',
    'doctor': 'health',
    'hospital': 'health',
    'pharmacy': 'health',
    
    # Bills
    'bills': 'bills',
    'bill': 'bills',
    'electricity': 'bills',
    'water': 'bills',
    'internet': 'bills',
    'phone': 'bills',
    'rent': 'bills'
}

def parse_amount_currency_category(text: str) -> Dict[str, Any]:
    """
    Parse expense text and extract amount, currency, category, and note.
    
    Args:
        text: Input text like "Spent 100 on lunch" or "৳100 coffee"
        
    Returns:
        Dict with keys: amount (Decimal), currency (str), category (str), note (str)
        Returns empty dict if no amount found.
    """
    if not text or not text.strip():
        return {}
    
    text_clean = text.strip()
    result = {
        'amount': None,
        'currency': 'BDT',  # Default currency
        'category': 'general',  # Default category
        'note': text_clean
    }
    
    # Step 1: Extract amount and currency
    amount_found = False
    
    # Try currency symbols first (highest priority)
    for symbol, currency_code in CURRENCY_SYMBOLS.items():
        pattern = rf'{re.escape(symbol)}\s*(\d+(?:\.\d{{1,2}})?)'
        match = re.search(pattern, text_clean)
        if match:
            result['amount'] = Decimal(match.group(1))
            result['currency'] = currency_code
            amount_found = True
            break
    
    # Try spent/paid/bought patterns
    if not amount_found:
        action_pattern = re.compile(r'(?i)\b(spent|paid|bought)\b.*?(\d+(?:\.\d{1,2})?)')
        match = action_pattern.search(text_clean)
        if match:
            result['amount'] = Decimal(match.group(2))
            amount_found = True
            
            # Check for currency words near the amount
            currency_found = False
            for word, currency_code in CURRENCY_WORDS.items():
                if word.lower() in text_clean.lower():
                    result['currency'] = currency_code
                    currency_found = True
                    break
    
    # Try amount + on/for patterns
    if not amount_found:
        preposition_pattern = re.compile(r'(?i)\b(?:tk|৳|bdt|usd|eur|inr|rs|rs\.)?\s*(\d+(?:\.\d{1,2})?)\b.*?\b(on|for)\b')
        match = preposition_pattern.search(text_clean)
        if match:
            result['amount'] = Decimal(match.group(1))
            amount_found = True
            
            # Extract currency if present
            currency_part = match.group(0).split(match.group(1))[0].strip()
            for word, currency_code in CURRENCY_WORDS.items():
                if word.lower() in currency_part.lower():
                    result['currency'] = currency_code
                    break
    
    # If no amount found, return empty dict
    if not amount_found:
        return {}
    
    # Step 2: Extract category
    # Look for word after "on" or "for"
    category_pattern = re.compile(r'(?i)\b(?:on|for)\s+(\w+)')
    category_match = category_pattern.search(text_clean)
    
    if category_match:
        category_word = category_match.group(1).lower()
        # Map to normalized category
        if category_word in CATEGORY_ALIASES:
            result['category'] = CATEGORY_ALIASES[category_word]
        else:
            result['category'] = category_word
    else:
        # Try to find category keywords anywhere in text
        text_lower = text_clean.lower()
        for keyword, category in CATEGORY_ALIASES.items():
            if keyword in text_lower:
                result['category'] = category
                break
    
    return result

def test_parse_amount_currency_category():
    """Test cases for unified parser"""
    test_cases = [
        # Basic patterns
        ("Spent 100 on lunch", {'amount': Decimal('100'), 'currency': 'BDT', 'category': 'food'}),
        ("৳100 coffee", {'amount': Decimal('100'), 'currency': 'BDT', 'category': 'food'}),
        ("paid $25 for transport", {'amount': Decimal('25'), 'currency': 'USD', 'category': 'transport'}),
        ("bought €30 groceries", {'amount': Decimal('30'), 'currency': 'EUR', 'category': 'groceries'}),
        ("100 tk for lunch", {'amount': Decimal('100'), 'currency': 'BDT', 'category': 'food'}),
        ("₹200 on dinner", {'amount': Decimal('200'), 'currency': 'INR', 'category': 'food'}),
        
        # Decimal amounts
        ("spent 150.50 on shopping", {'amount': Decimal('150.50'), 'currency': 'BDT', 'category': 'shopping'}),
        ("£15.99 for books", {'amount': Decimal('15.99'), 'currency': 'GBP', 'category': 'general'}),
        
        # No amount cases
        ("summary", {}),
        ("hello", {}),
        ("", {}),
    ]
    
    all_passed = True
    for text, expected in test_cases:
        result = parse_amount_currency_category(text)
        
        if not expected:  # Empty dict expected
            if result:
                print(f"FAIL: parse_amount_currency_category('{text}') = {result}, expected empty dict")
                all_passed = False
            else:
                print(f"PASS: parse_amount_currency_category('{text}') = empty (correct)")
        else:
            # Check key fields
            matches = True
            for key in ['amount', 'currency', 'category']:
                if key in expected:
                    if result.get(key) != expected[key]:
                        print(f"FAIL: parse_amount_currency_category('{text}') {key} = {result.get(key)}, expected {expected[key]}")
                        matches = False
                        all_passed = False
            
            if matches:
                print(f"PASS: parse_amount_currency_category('{text}') = correct")
    
    return all_passed

if __name__ == "__main__":
    print("Testing parse_amount_currency_category() function:")
    test_parse_amount_currency_category()