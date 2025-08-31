"""
Enhanced Expense Parser for FinBrain
Handles natural language expense parsing with correction context support
"""

import re
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger("parsers.expense")

# Currency mappings
CURRENCY_SYMBOLS = {
    '৳': 'BDT',
    '$': 'USD', 
    '£': 'GBP',
    '€': 'EUR',
    '₹': 'INR',
    'Rs': 'INR',
    'Rs.': 'INR'
}

CURRENCY_WORDS = {
    'taka': 'BDT',
    'tk': 'BDT',
    'bdt': 'BDT',
    'dollar': 'USD',
    'usd': 'USD',
    'pound': 'GBP',
    'gbp': 'GBP',
    'euro': 'EUR',
    'eur': 'EUR',
    'rupee': 'INR',
    'inr': 'INR'
}

# Bangla numerals mapping
BANGLA_NUMERALS = {
    '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
    '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
}

# Category aliases for intelligent matching
CATEGORY_ALIASES = {
    # Food & Dining (strength: 10)
    'food': ('food', 10),
    'lunch': ('food', 9),
    'dinner': ('food', 9),
    'breakfast': ('food', 9),
    'coffee': ('food', 8),
    'tea': ('food', 8),
    'juice': ('food', 9),
    'fruit': ('food', 9),
    'water': ('food', 8),
    'milk': ('food', 8),
    'drink': ('food', 8),
    'beverage': ('food', 8),
    'soda': ('food', 8),
    'smoothie': ('food', 9),
    'shake': ('food', 9),
    'lassi': ('food', 9),
    'borhani': ('food', 9),
    'drank': ('food', 8),
    'drinking': ('food', 8),
    'restaurant': ('food', 9),
    'meal': ('food', 9),
    # Bengali Food Items - ADDED FOR KHICHURI ISSUE
    'khichuri': ('food', 10),
    'rice': ('food', 9),
    'dal': ('food', 9),
    'curry': ('food', 9),
    'biriyani': ('food', 10),
    'chicken': ('food', 9),
    'beef': ('food', 9),
    'fish': ('food', 9),
    'vegetable': ('food', 8),
    'egg': ('food', 8),
    'omelette': ('food', 9),
    'omelet': ('food', 9),
    'steak': ('food', 9),
    'brunch': ('food', 9),
    'snack': ('food', 8),
    'pizza': ('food', 9),
    'burger': ('food', 9),
    'sandwich': ('food', 9),
    'soup': ('food', 8),
    'salad': ('food', 8),
    'pasta': ('food', 8),
    'noodles': ('food', 8),
    'bread': ('food', 8),
    'cake': ('food', 8),
    'dessert': ('food', 8),
    
    # Transport (strength: 9)
    'transport': ('transport', 9),
    'taxi': ('transport', 10),
    'uber': ('transport', 10),
    'bus': ('transport', 9),
    'fuel': ('transport', 8),
    'cng': ('transport', 10),
    
    # Shopping (strength: 8)
    'shopping': ('shopping', 8),
    'clothes': ('shopping', 9),
    'grocery': ('shopping', 10),
    
    # Health (strength: 9)
    'health': ('health', 9),
    'medicine': ('health', 10),
    'pharmacy': ('health', 9),
    'doctor': ('health', 9),
    
    # Bills (strength: 9) - ENHANCED FOR GAS BILL ISSUE
    'internet': ('bills', 10),
    'phone': ('bills', 9),
    'rent': ('bills', 10),
    'utilities': ('bills', 9),
    'gas bill': ('bills', 10),  # Utility gas bill
    'electricity bill': ('bills', 10),
    'water bill': ('bills', 10),
    'electric bill': ('bills', 10),
    'power bill': ('bills', 10),
    'utility bill': ('bills', 10),
    
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
    'tuition': ('education', 10),
    
    # Pets & Animals (strength: 9) - ADDED FOR CAT FOOD ISSUE
    'pet': ('pets', 10),
    'pets': ('pets', 10),
    'cat': ('pets', 9),
    'dog': ('pets', 9),
    'animal': ('pets', 8),
    'vet': ('pets', 9),
    'veterinary': ('pets', 9),
    'cat food': ('pets', 10),
    'dog food': ('pets', 10),
    'pet food': ('pets', 10),
    'pet supplies': ('pets', 9),
    'pet store': ('pets', 9)
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
    r'\b(?:sorry|i meant|meant|actually|replace last|correct that|correction|should be|update to|make it|not\s+\d+|typo|correct|please correct|fix|change|wrong|incorrect|mistake|edit|can you correct)\b',
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

def extract_all_expenses(text: str, now: Optional[datetime] = None, **kwargs) -> List[Dict[str, Any]]:
    """
    Extract all expenses from text that may contain multiple amounts.
    
    Args:
        text: Input text to parse (e.g., "Uber 2500 and breakfast 700")
        now: Current timestamp for date resolution
        
    Returns:
        List of expense dicts, each with keys: amount, currency, category, merchant, ts_client, note
    """
    if not text or not text.strip():
        return []
    
    if now is None:
        now = datetime.now()
    
    # Normalize text for better parsing
    normalized = normalize_text_for_parsing(text)
    expenses = []
    
    # Find all amounts in the text (symbols, words, bare numbers) - ENHANCED FOR COMMA PARSING
    amount_patterns = [
        # Currency symbols with amounts (enhanced for comma handling)
        (r'([৳$£€₹])\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)', 'symbol'),
        # Amount with currency words (enhanced for comma handling)
        (r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(tk|taka|bdt|usd|eur|inr|rs|dollar|pound|euro|rupee)\b', 'word'),
        # Action verbs with amounts (enhanced for comma handling)
        (r'\b(spent|paid|bought|blew|burned|used)\s+[^\d]*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)', 'verb'),
        # Category + amount patterns (enhanced for comma handling)
        (r'\b(coffee|lunch|dinner|breakfast|uber|taxi|cng|bus|grocery|groceries|medicine|pharmacy)\s+(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)', 'category'),
        # Bare numbers (enhanced for comma handling)
        (r'\b(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d{2,7}(?:\.\d{1,2})?)\b', 'bare')
    ]
    
    found_amounts = []
    
    for pattern, pattern_type in amount_patterns:
        matches = re.finditer(pattern, normalized, re.IGNORECASE)
        for match in matches:
            if pattern_type == 'symbol':
                symbol, amount_str = match.groups()
                currency = CURRENCY_SYMBOLS.get(symbol, 'BDT')
                amount_val = amount_str
            elif pattern_type == 'word':
                amount_val, currency_word = match.groups()
                currency = CURRENCY_WORDS.get(currency_word.lower(), 'BDT')
            elif pattern_type == 'verb':
                amount_val = match.group(2)
                currency = 'BDT'  # Default
            elif pattern_type == 'category':
                category_word, amount_val = match.groups()
                currency = 'BDT'  # Default
            else:  # bare
                amount_val = match.group(1)
                currency = 'BDT'  # Default
            
            try:
                # Fix comma decimal parsing - handle thousands vs decimal separators
                amount = _parse_amount_with_locale_support(amount_val)
                
                # Add database overflow protection
                if amount <= 0 or amount >= Decimal('99999999.99'):  # Skip invalid amounts
                    continue
                
                found_amounts.append({
                    'amount': amount,
                    'currency': currency,
                    'start': match.start(),
                    'end': match.end(),
                    'context_start': max(0, match.start() - 50),
                    'context_end': min(len(text), match.end() + 50)
                })
            except (InvalidOperation, ValueError):
                continue
    
    # Remove duplicate amounts at same position
    unique_amounts = []
    for amount_info in found_amounts:
        is_duplicate = False
        for existing in unique_amounts:
            if (abs(amount_info['start'] - existing['start']) < 10 and 
                amount_info['amount'] == existing['amount']):
                is_duplicate = True
                break
        if not is_duplicate:
            unique_amounts.append(amount_info)
    
    # For each amount, infer category from targeted context
    for amount_info in unique_amounts:
        # Extract targeted context specific to this amount (fix multi-expense categories)
        context_text = _extract_targeted_context(text, amount_info)
        
        # Infer category from context with user learning integration  
        user_hash = kwargs.get('user_hash')  # Extract user hash from kwargs if passed
        category = _infer_category_from_context(context_text, user_hash)
        
        # Extract merchant if present in context
        merchant = extract_merchant(context_text)
        
        # Extract date context
        date_context = extract_date_context(text, now)
        
        expense = {
            'amount': amount_info['amount'].quantize(Decimal('0.01')),
            'currency': amount_info['currency'],
            'category': category,
            'merchant': merchant,
            'ts_client': date_context or now,
            'note': text.strip()
        }
        expenses.append(expense)
    
    return expenses

def _parse_amount_with_locale_support(amount_str: str) -> Decimal:
    """
    Parse amount string with proper comma/decimal handling.
    
    Args:
        amount_str: Amount string like "1,250.50" or "2,500" or "4.50"
        
    Returns:
        Decimal amount
        
    Examples:
        "1,250.50" → 1250.50 (thousands separator + decimal)
        "2,500" → 2500.00 (thousands separator only)
        "4.50" → 4.50 (decimal only)
        "1.25" → 1.25 (decimal only, ambiguous but treat as decimal)
    """
    if not amount_str:
        raise ValueError("Empty amount string")
    
    # Remove spaces
    amount_str = amount_str.strip()
    
    # Check for decimal format patterns
    if ',' in amount_str and '.' in amount_str:
        # Both comma and period present - comma is thousands separator
        # Example: "1,250.50" → 1250.50
        amount_str = amount_str.replace(',', '')
        return Decimal(amount_str)
    elif ',' in amount_str:
        # Only comma present - check if it's thousands separator or decimal
        parts = amount_str.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Likely decimal separator: "4,50" → 4.50
            amount_str = amount_str.replace(',', '.')
        else:
            # Likely thousands separator: "2,500" → 2500
            amount_str = amount_str.replace(',', '')
    # If only period, treat as decimal separator (no change needed)
    
    return Decimal(amount_str)

def _extract_targeted_context(text: str, amount_info: dict) -> str:
    """
    Extract targeted context around a specific amount for better category inference.
    
    Args:
        text: Full text
        amount_info: Dict with amount position info
        
    Returns:
        Targeted context string focused on this specific amount
    """
    amount_start = amount_info['start']
    amount_end = amount_info['end']
    
    # Look for word boundaries around the amount to create focused context
    words = text.split()
    text_positions = []
    current_pos = 0
    
    # Map word positions to character positions
    for word in words:
        word_start = text.find(word, current_pos)
        word_end = word_start + len(word)
        text_positions.append((word, word_start, word_end))
        current_pos = word_end
    
    # Find words near the amount (±3 words)
    target_words = []
    amount_word_index = -1
    
    # Find which word contains our amount
    for i, (word, start, end) in enumerate(text_positions):
        if start <= amount_start < end or start < amount_end <= end:
            amount_word_index = i
            break
    
    if amount_word_index >= 0:
        # Take ±3 words around the amount word
        start_idx = max(0, amount_word_index - 3)
        end_idx = min(len(text_positions), amount_word_index + 4)
        target_words = [pos[0] for pos in text_positions[start_idx:end_idx]]
    else:
        # Fallback to character-based context if word mapping fails
        context_start = max(0, amount_start - 30)
        context_end = min(len(text), amount_end + 30)
        return text[context_start:context_end]
    
    return ' '.join(target_words)

def _infer_category_from_context(context_text: str, user_hash: str = None) -> str:
    """
    Infer category from context text using a ±6 word window with user learning integration.
    
    Args:
        context_text: Text context around the amount
        user_hash: User's hash for checking learned preferences
        
    Returns:
        Inferred category string
    """
    if not context_text:
        return 'general'
    
    context_lower = context_text.lower()
    best_category = 'general'
    best_strength = 0
    
    # PRIORITY 1: Check user's learned preferences first
    if user_hash:
        try:
            from utils.expense_learning import user_learning_system
            # Extract potential item names from context
            words = context_lower.split()
            for word in words:
                if len(word) > 2:  # Skip short words
                    user_pref = user_learning_system.get_user_preference(user_hash, word)
                    if user_pref:
                        # User has explicitly learned this - use it with highest priority
                        return user_pref['category']
            
            # Also check multi-word items like "rc cola"
            for i in range(len(words) - 1):
                two_word_item = f"{words[i]} {words[i+1]}"
                user_pref = user_learning_system.get_user_preference(user_hash, two_word_item)
                if user_pref:
                    return user_pref['category']
        except Exception as e:
            # Don't fail parsing if learning system has issues
            pass
    
    # Enhanced category matching with context-specific boosts
    category_keywords = {
        # Bills - HIGHEST PRIORITY FOR UTILITY BILLS
        'bills': ['gas bill', 'electricity bill', 'electric bill', 'water bill', 'power bill', 'utility bill', 'internet bill', 'phone bill', 'rent', 'utilities'],
        # Transport (strong indicators) - NOTE: 'gas' alone can be fuel, but 'gas bill' is above  
        'transport': ['uber', 'taxi', 'cng', 'bus', 'ride', 'lyft', 'grab', 'pathao', 'fuel', 'petrol', 'gas station', 'gas pump', 'paid gas', 'gas tank', 'fill gas', 'filled gas'],
        # Pets & Animals - MOVED BEFORE FOOD FOR PRIORITY IN CAT FOOD ISSUE
        'pets': ['cat', 'dog', 'pet', 'pets', 'animal', 'vet', 'veterinary', 'cat food', 'dog food', 'pet food', 'pet supplies', 'pet store'],
        # Food (strong indicators) - ADDED BENGALI FOODS + DRINKS FOR JUICE ISSUE + BRUNCH/OMELETTE FIX
        'food': ['breakfast', 'lunch', 'dinner', 'brunch', 'coffee', 'tea', 'restaurant', 'meal', 'pizza', 'burger', 'food', 
                 'juice', 'fruit', 'water', 'milk', 'drink', 'beverage', 'soda', 'smoothie', 'shake', 'lassi', 'borhani', 
                 'drank', 'drinking', 'khichuri', 'rice', 'dal', 'curry', 'biriyani', 'chicken', 'beef', 'fish', 'vegetable', 'egg',
                 'omelette', 'omelet', 'steak', 'snack', 'sandwich', 'soup', 'salad', 'pasta', 'noodles', 'bread', 'cake', 'dessert'],
        # Shopping
        'shopping': ['shopping', 'clothes', 'grocery', 'groceries', 'market', 'store', 'buy', 'bought'],
        # Health
        'health': ['medicine', 'pharmacy', 'doctor', 'hospital', 'medical', 'health'],
        # Bills
        'bills': ['internet', 'phone', 'rent', 'utilities', 'bill', 'electricity', 'water'],
        # Entertainment
        'entertainment': ['movie', 'cinema', 'game', 'entertainment', 'travel', 'vacation']
    }
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in context_lower:
                # Base strength
                strength = 8
                
                # Boost if keyword appears multiple times
                if context_lower.count(keyword) > 1:
                    strength += 2
                
                # Boost for exact category matches
                if keyword in ['uber', 'taxi', 'breakfast', 'lunch', 'dinner', 'grocery']:
                    strength += 3
                    
                # Extra boost for pet-specific keywords to override generic "food"
                if keyword in ['cat', 'dog', 'cat food', 'dog food', 'pet food', 'vet']:
                    strength += 5
                
                if strength > best_strength:
                    best_strength = strength
                    best_category = category
    
    return best_category

def parse_expense(text: str, now: datetime, correction_context: bool = False) -> Optional[Dict[str, Any]]:
    """
    Enhanced expense parser with correction context support.
    Preserved for backward compatibility - returns first expense from extract_all_expenses.
    
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
    
    # For correction context, support bare numbers and k shorthand
    if correction_context:
        # Normalize text for better parsing
        normalized = normalize_text_for_parsing(text)
        
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
    
    # Use multi-expense parser and return first result
    all_expenses = extract_all_expenses(text, now)
    return all_expenses[0] if all_expenses else None

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