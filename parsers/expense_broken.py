"""
Enhanced Unified Expense Parser: Robust NLP for STD and AI modes
Implements parse_expense() with comprehensive merchant extraction and multilingual support
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
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

# Bangla numeral mapping
BANGLA_NUMERALS = {
    '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
    '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
}

# Enhanced category mapping with strength scoring
CATEGORY_ALIASES = {
    # Food & Dining (strength: 10)
    'lunch': ('food', 10),
    'dinner': ('food', 10), 
    'breakfast': ('food', 10),
    'coffee': ('food', 10),
    'meal': ('food', 9),
    'snack': ('food', 8),
    'tea': ('food', 8),
    'restaurant': ('food', 9),
    'cafe': ('food', 9),
    'café': ('food', 9),
    'food': ('food', 8),
    
    # Transport (strength: 10)
    'uber': ('transport', 10),
    'taxi': ('transport', 10),
    'bus': ('transport', 10),
    'ride': ('transport', 9),
    'fuel': ('transport', 10),
    'petrol': ('transport', 10),
    'transport': ('transport', 8),
    'cab': ('transport', 9),
    'cng': ('transport', 9),
    'rickshaw': ('transport', 8),
    
    # Groceries (strength: 10)
    'grocery': ('groceries', 10),
    'groceries': ('groceries', 10),
    'market': ('groceries', 9),
    'vegetables': ('groceries', 9),
    'fruits': ('groceries', 9),
    
    # Health (strength: 10)
    'medicine': ('health', 10),
    'pharmacy': ('health', 10),
    'doctor': ('health', 9),
    'hospital': ('health', 9),
    'meds': ('health', 9),
    'chemist': ('health', 9),
    
    # Shopping (strength: 8)
    'shopping': ('shopping', 8),
    'clothes': ('shopping', 9),
    'shirt': ('shopping', 8),
    'dress': ('shopping', 8),
    'shoes': ('shopping', 8),
    
    # Bills & Utilities (strength: 9)
    'bills': ('bills', 9),
    'bill': ('bills', 9),
    'electricity': ('bills', 10),
    'water': ('bills', 10),
    'internet': ('bills', 10),
    'phone': ('bills', 9),
    'rent': ('bills', 10),
    'utilities': ('bills', 9),
    
    # Entertainment (strength: 8)
    'entertainment': ('entertainment', 8),
    'movie': ('entertainment', 9),
    'cinema': ('entertainment', 9),
    'game': ('entertainment', 8),
    'travel': ('entertainment', 8),
    
    # Kids & Education (strength: 9)
    'kids': ('family', 9),
    'baby': ('family', 9),
    'education': ('education', 10),
    'school': ('education', 9),
    'tuition': ('education', 10)
}

def normalize_text_for_parsing(text: str) -> str:
    """
    Normalize text for parsing: handle Bangla numerals, clean spacing, handle multipliers.
    """
    if not text:
        return ""
    
    normalized = text
    
    # Convert Bangla numerals to ASCII
    for bangla, ascii_num in BANGLA_NUMERALS.items():
        normalized = normalized.replace(bangla, ascii_num)
    
    # Handle k/K shorthand multipliers
    k_pattern = re.compile(r'(\d+(?:\.\d+)?)k\b', re.IGNORECASE)
    for match in k_pattern.finditer(normalized):
        original = match.group(0)
        number = float(match.group(1)) * 1000
        # Replace 1.2k with 1200, preserve context
        normalized = normalized.replace(original, str(int(number) if number.is_integer() else number))
    
    # Normalize spacing and remove artifacts
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s$£€₹৳.,()-]', ' ', normalized)
    
    return normalized.strip()

# Correction message patterns
CORRECTION_PATTERNS = re.compile(
    r'\b(?:sorry|i meant|meant|actually|replace last|correct that|correction|should be|update to|make it|not\s+\d+|typo)\b',
    re.IGNORECASE
)

def is_correction_message(text: str) -> bool:
    """
    Check if text contains correction patterns.
    
    Args:
        text: Input text to check
        
    Returns:
        True if correction patterns detected, False otherwise
    """
    if not text or not text.strip():
        return False
    
    return bool(CORRECTION_PATTERNS.search(text.lower()))

def parse_correction_reason(text: str) -> str:
    """
    Extract correction reason from correction text.
    
    Args:
        text: Correction message text
        
    Returns:
        Cleaned correction reason phrase
    """
    if not text:
        return "user correction"
    
    # Extract the correction phrase
    match = CORRECTION_PATTERNS.search(text.lower())
    if match:
        return match.group().strip()
    
    return "user correction"

def similar_category(cat1: str, cat2: str) -> bool:
    """
    Check if two categories are similar for correction candidate matching.
    
    Args:
        cat1: First category
        cat2: Second category
        
    Returns:
        True if categories are similar, False otherwise
    """
    if not cat1 or not cat2:
        return False
    
    return cat1.lower() == cat2.lower()

def similar_merchant(merchant1: str, merchant2: str) -> bool:
    """
    Check if two merchants are similar for correction candidate matching.
    
    Args:
        merchant1: First merchant
        merchant2: Second merchant
        
    Returns:
        True if merchants are similar, False otherwise
    """
    if not merchant1 or not merchant2:
        return False
    
    # Case-insensitive contains check
    return (merchant1.lower() in merchant2.lower() or 
            merchant2.lower() in merchant1.lower())

def parse_expense(text: str, now: datetime, correction_context: bool = False) -> Optional[Dict[str, Any]]:
    """
    Enhanced expense parser with correction context support.
    
    Args:
        text: Input text to parse
        now: Current timestamp for date resolution
        correction_context: True if parsing a correction message
        
    Returns:
        Dict with keys: amount, currency, category, merchant, ts_client, note
        Returns None if no valid expense found
    """
    if not text or not text.strip():
        return None
    
    # Normalize text for better parsing
    normalized = normalize_text_for_parsing(text)
    
    # For correction context, support bare numbers and k shorthand
    if correction_context:
        # Pattern 1: Bare numbers (allow None for other fields to be inherited)
        bare_number_match = re.search(r'\b(\d{1,7}(?:[.,]\d{1,2})?)\b', normalized)
        if bare_number_match:
            try:
                amount = Decimal(bare_number_match.group(1).replace(',', '.'))
                return {
                    'amount': amount,
                    'currency': None,  # Will be inherited from candidate
                    'category': None,  # Will be inherited from candidate  
                    'merchant': None,  # Will be inherited from candidate
                    'ts_client': now,
                    'note': text.strip(),
                    'correction_context': True
                }
            except (InvalidOperation, ValueError):
                pass
    
    # Standard parsing logic continues...
    return _parse_standard_expense(normalized, text, now)

def extract_merchant(text: str) -> Optional[str]:
    """
    Extract merchant name from text using patterns like "at", "in", "from".
    """
    # Look for merchant patterns
    merchant_patterns = [
        r'\b(?:at|in|from)\s+([^,;.!?\n]+?)(?:\s+(?:today|yesterday|this|last|next|summary|insight|and|but|because)|\s*[,.!?;]|$)',
        r'\b(?:at|in|from)\s+([A-Z][^,;.!?\n]*?)(?:\s+(?:today|yesterday)|\s*[,.!?;]|$)'
    ]
    
    for pattern in merchant_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            
            # Clean up the merchant name
            # Remove leading articles
            merchant = re.sub(r'^(?:the|a|an)\s+', '', merchant, flags=re.IGNORECASE)
            
            # Title case for better presentation
            merchant = ' '.join(word.capitalize() for word in merchant.split())
            
            if len(merchant) > 2:  # Avoid single letters
                return merchant
    
    return None

def extract_date_context(text: str, now_ts: datetime) -> Optional[datetime]:
    """
    Extract date context from text (today, yesterday, last night, etc.).
    """
    text_lower = text.lower()
    
    if any(term in text_lower for term in ['yesterday', 'last night']):
        # Return yesterday at midnight
        yesterday = now_ts - timedelta(days=1)
        return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if any(term in text_lower for term in ['this morning', 'earlier today']):
        # Return today at 8 AM
        return now_ts.replace(hour=8, minute=0, second=0, microsecond=0)
    
    # Default to None (use current timestamp)
    return None

def infer_category_with_strength(text: str) -> str:
    """
    Infer category from text with strength-based scoring.
    """
    text_lower = text.lower()
    best_category = 'general'
    best_strength = 0
    
    # Check each category alias
    for keyword, (category, strength) in CATEGORY_ALIASES.items():
        if keyword in text_lower:
            # Boost strength if word appears after "on" or "for"
            boost_pattern = rf'\b(?:on|for)\s+\w*\b{re.escape(keyword)}\b'
            if re.search(boost_pattern, text_lower):
                strength += 2
            
            if strength > best_strength:
                best_strength = strength
                best_category = category
    
    return best_category

def _parse_standard_expense(normalized: str, original_text: str, now_ts: datetime) -> Optional[Dict[str, Any]]:
    """
    Standard expense parsing logic.
    
    Args:
        normalized: Normalized text for parsing
        original_text: Original input text
        now_ts: Current timestamp for date resolution
        
    Returns:
        Dict with parsed expense data or None if no valid expense found
    """
    normalized_text = normalized
    
    result = {
        'amount': None,
        'currency': 'BDT',  # Default to BDT
        'category': 'general',
        'merchant': None,
        'ts_client': None,
        'note': original_text
    }
    
    # Step 1: Extract amount and currency
    amount_found = False
    
    # Try currency symbols first (highest priority)
    for symbol, currency_code in CURRENCY_SYMBOLS.items():
        pattern = rf'{re.escape(symbol)}\s*(\d+(?:\.\d{{1,2}})?)'
        match = re.search(pattern, normalized_text)
        if match:
            try:
                result['amount'] = Decimal(match.group(1))
                result['currency'] = currency_code
                amount_found = True
                break
            except InvalidOperation:
                continue
    
    # Try currency words
    if not amount_found:
        for word, currency_code in CURRENCY_WORDS.items():
            # Pattern: amount + currency word OR currency word + amount
            patterns = [
                rf'\b(\d+(?:\.\d{{1,2}})?)\s*{re.escape(word)}\b',
                rf'\b{re.escape(word)}\s*(\d+(?:\.\d{{1,2}})?)\b'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, normalized_text, re.IGNORECASE)
                if match:
                    try:
                        result['amount'] = Decimal(match.group(1))
                        result['currency'] = currency_code
                        amount_found = True
                        break
                    except InvalidOperation:
                        continue
            
            if amount_found:
                break
    
    # Try action verbs (spent, paid, bought, etc.)
    if not amount_found:
        action_pattern = re.compile(r'\b(spent|paid|bought|blew|burned|used)\b.*?(\d+(?:\.\d{1,2})?)', re.IGNORECASE)
        match = action_pattern.search(normalized_text)
        if match:
            try:
                result['amount'] = Decimal(match.group(2))
                amount_found = True
            except InvalidOperation:
                pass
    
    # Try first numeric token as fallback
    if not amount_found:
        # Find first number that's not a year or date
        number_pattern = re.compile(r'\b(\d+(?:\.\d{1,2})?)\b')
        for match in number_pattern.finditer(normalized_text):
            num_str = match.group(1)
            num_val = float(num_str)
            
            # Skip if looks like a year (1900-2100)
            if 1900 <= num_val <= 2100:
                continue
            
            # Skip if followed by month names
            following_text = normalized_text[match.end():match.end()+20].lower()
            if any(month in following_text for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                                        'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                continue
            
            try:
                result['amount'] = Decimal(num_str)
                amount_found = True
                break
            except InvalidOperation:
                continue
    
    # If no amount found, return None
    if not amount_found or not result['amount']:
        return None
    
    # Step 2: Extract merchant
    result['merchant'] = extract_merchant(original_text)
    
    # Step 3: Infer category
    result['category'] = infer_category_with_strength(original_text)
    
    # Step 4: Extract date context
    date_context = extract_date_context(original_text, now_ts)
    if date_context:
        result['ts_client'] = date_context
    else:
        result['ts_client'] = now_ts
    
    # Clip amount to two decimal places
    result['amount'] = result['amount'].quantize(Decimal('0.01'))
    
    return result

# ========================================
# CORRECTION PARSING FUNCTIONS
# ========================================

# Correction phrase patterns (case-insensitive, compiled for performance)
CORRECTION_PATTERNS = re.compile(
    r'\b(?:sorry|i meant|meant|actually|correction|correct that|replace last|change that|'
    r'not (?:\d+|\$\d+|৳\d+)|should be|make it|update to|typo|fix|replace|change)\b',
    re.IGNORECASE
)

def is_correction_message(text: str) -> bool:
    """
    Check if message contains correction phrases.
    
    Args:
        text: User message text
        
    Returns:
        True if message contains correction indicators
    """
    if not text or not text.strip():
        return False
        
    # Must contain correction phrases AND money amounts
    has_correction_phrase = bool(CORRECTION_PATTERNS.search(text))
    from finbrain.router import contains_money
    has_money = contains_money(text)
    
    return has_correction_phrase and has_money

def parse_correction_reason(text: str) -> str:
    """
    Extract short correction reason from correction message.
    
    Args:
        text: User correction message
        
    Returns:
        Short reason string (max 50 chars)
    """
    text_lower = text.lower().strip()
    
    # Common correction patterns
    if 'sorry' in text_lower and 'meant' in text_lower:
        return "sorry, i meant"
    elif 'meant' in text_lower:
        return "meant"
    elif 'actually' in text_lower:
        return "actually"
    elif 'typo' in text_lower:
        return "typo fix"
    elif 'correct' in text_lower:
        return "correction"
    elif 'replace' in text_lower:
        return "replace"
    elif 'should be' in text_lower:
        return "should be"
    else:
        return "amount correction"

def similar_category(cat_a: str, cat_b: str) -> bool:
    """
    Check if two categories are similar (loose matching).
    
    Args:
        cat_a: First category
        cat_b: Second category
        
    Returns:
        True if categories are similar
    """
    if not cat_a or not cat_b:
        return False
    
    # Exact match (case-insensitive)
    if cat_a.lower().strip() == cat_b.lower().strip():
        return True
    
    # Parent category matching (food vs food delivery)
    parent_cats = {
        'food', 'transport', 'entertainment', 'bills', 'shopping', 
        'health', 'education', 'family', 'general'
    }
    
    for parent in parent_cats:
        if parent in cat_a.lower() and parent in cat_b.lower():
            return True
    
    return False

def similar_merchant(merchant_a: str, merchant_b: str) -> bool:
    """
    Check if two merchants are similar (fuzzy matching).
    
    Args:
        merchant_a: First merchant
        merchant_b: Second merchant
        
    Returns:
        True if merchants are similar
    """
    if not merchant_a or not merchant_b:
        return False
    
    # Normalize
    a = merchant_a.lower().strip()
    b = merchant_b.lower().strip()
    
    # Exact match
    if a == b:
        return True
    
    # Substring matching (either direction)
    if len(a) >= 3 and len(b) >= 3:
        return a in b or b in a
    
    return False

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
    
    # Use the main parse_expense function and adapt the result
    result = parse_expense(text, datetime.now())
    if not result:
        return {}
    
    return {
        'amount': result.get('amount'),
        'currency': result.get('currency', 'BDT'),
        'category': result.get('category', 'general'),
        'note': result.get('note', text.strip())
    }
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