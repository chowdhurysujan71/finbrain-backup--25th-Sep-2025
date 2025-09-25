"""
Expense parser: Extracts amounts and categories from text
"""
import re
from typing import Any, Dict, List

# Pattern for amounts with optional currency
AMOUNT_PATTERN = r'(\d+(?:\.\d{1,2})?)\s*(?:bdt|tk|taka|usd)?'

# Category keywords mapping
CATEGORY_KEYWORDS = {
    'food': ['food', 'lunch', 'dinner', 'breakfast', 'brunch', 'meal', 'snack', 'coffee', 'tea', 'restaurant', 
             'omelette', 'omelet', 'steak', 'beef', 'chicken', 'fish', 'pizza', 'burger', 'sandwich', 
             'soup', 'salad', 'pasta', 'noodles', 'bread', 'cake', 'dessert', 'juice', 'milk'],
    'groceries': ['grocery', 'groceries', 'market', 'vegetables', 'fruits'],
    'transport': ['uber', 'ride', 'transport', 'taxi', 'bus', 'train', 'gas', 'fuel'],
    'shopping': ['shopping', 'clothes', 'shoe', 'shoes', 'dress', 'shirt', 'pants'],
    'bills': ['bill', 'electricity', 'water', 'internet', 'phone', 'rent'],
    'entertainment': ['movie', 'cinema', 'entertainment', 'fun', 'game'],
    'health': ['medicine', 'doctor', 'hospital', 'pharmacy', 'health'],
}

def extract_expenses(text: str) -> list[dict[str, Any]]:
    """
    Extract expense amounts and categories from text
    Returns list of dicts with 'amount' and 'category' keys
    """
    if not text:
        return []
    
    text_lower = text.lower()
    expenses = []
    
    # Find all amounts in text
    amounts = re.findall(AMOUNT_PATTERN, text_lower)
    
    if not amounts:
        return []
    
    # Try to match categories for each amount
    for i, amount_str in enumerate(amounts):
        amount = float(amount_str)
        
        # Find category based on keywords
        category = 'other'
        
        # Check for specific keywords around this amount
        # Look for context words near the amount
        amount_pos = text_lower.find(amount_str)
        context_start = max(0, amount_pos - 20)
        context_end = min(len(text_lower), amount_pos + 20)
        context = text_lower[context_start:context_end]
        
        # Check categories in context
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in context for kw in keywords):
                category = cat
                break
        
        # Look for explicit category mentions near the amount
        # Pattern: "100 on food" or "food 100"
        amount_context = re.search(
            rf'{amount_str}\s+(?:on|for)\s+(\w+)|(\w+)\s+{amount_str}',
            text_lower
        )
        if amount_context:
            word = amount_context.group(1) or amount_context.group(2)
            for cat, keywords in CATEGORY_KEYWORDS.items():
                if word in keywords:
                    category = cat
                    break
        
        expenses.append({
            'amount': amount,
            'category': category,
            'description': f'Expense from: {text[:50]}'
        })
    
    return expenses

def parse_expense(text: str) -> tuple[float, str] | None:
    """
    Legacy parser for backward compatibility
    Returns (amount, description) tuple or None
    """
    expenses = extract_expenses(text)
    if expenses:
        exp = expenses[0]
        return (exp['amount'], exp.get('description', ''))
    return None