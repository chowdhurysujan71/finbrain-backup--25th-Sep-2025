"""
Normalized AI expense parsing with defensive handling
Fixes "function has no len()" errors through type safety
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def parse_expense(text: str) -> dict:
    """
    Returns {'amount': float, 'category': str, 'note': str|None}
    Raises ValueError on bad parse.
    """
    try:
        # Call the actual AI model (using existing AI adapter)
        from utils.ai_adapter_v2 import production_ai_adapter
        ai = production_ai_adapter
        result = ai.parse_expense(text) if hasattr(ai, 'parse_expense') else _fallback_parse(text)
    except Exception:
        # If AI adapter fails, use fallback parsing
        result = _fallback_parse(text)
    
    # Defensive normalization - exactly as specified
    if callable(result):
        result = result()  # or raise if that's unexpected
    if not isinstance(result, dict):
        raise ValueError(f"AI parse returned {type(result)}")
    
    amt = result.get("amount")
    cat = result.get("category")
    note = result.get("note")
    
    # Unwrap callables
    if callable(amt): amt = amt()
    if callable(cat): cat = cat()
    if callable(note): note = note()
    
    # Strict validation
    if amt is None or not isinstance(amt, (int, float, str)):
        raise ValueError("amount missing/invalid")
    if not cat or not isinstance(cat, str):
        raise ValueError("category missing/invalid")
    
    # Convert string amounts
    if isinstance(amt, str):
        try:
            amt = float(amt.replace(",", "").strip())
        except ValueError:
            raise ValueError("amount not convertible to number")
    
    return {
        "amount": float(amt), 
        "category": cat.strip(), 
        "note": (note or "").strip() or None
    }

def _fallback_parse(text: str) -> dict:
    """Simple fallback parsing when AI is unavailable"""
    import re
    
    # Extract numbers
    amounts = re.findall(r'(\d+(?:\.\d+)?)', text)
    if not amounts:
        raise ValueError("No amount found")
    
    amount = float(amounts[0])
    
    # Simple category detection
    text_lower = text.lower()
    if any(word in text_lower for word in ["coffee", "tea", "drink"]):
        category = "Food"
    elif any(word in text_lower for word in ["lunch", "dinner", "food", "meal"]):
        category = "Food"
    elif any(word in text_lower for word in ["gas", "fuel", "petrol"]):
        category = "Transport"
    elif any(word in text_lower for word in ["uber", "taxi", "bus", "parking"]):
        category = "Transport"
    else:
        category = "Other"
    
    return {"amount": amount, "category": category, "note": None}

def regex_parse(text: str) -> dict:
    """Very strict regex parser for fallback - matches 'spent 200 on groceries' format"""
    import re
    
    # Match patterns like "spent 200 on groceries" or "coffee 50"
    patterns = [
        r'spent\s+(\d+(?:\.\d+)?)\s+on\s+(.+)',
        r'(\w+)\s+(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s+(\w+)',
        r'(\d+(?:\.\d+)?)\s+for\s+(.+)'
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            groups = match.groups()
            
            # Determine which group is amount vs category
            if len(groups) == 2:
                try:
                    # Try first group as amount
                    amount = float(groups[0])
                    category = groups[1].strip().title()
                except ValueError:
                    try:
                        # Try second group as amount  
                        amount = float(groups[1])
                        category = groups[0].strip().title()
                    except ValueError:
                        continue
                
                if amount > 0 and category:
                    return {"amount": amount, "category": category, "note": None}
    
    return None  # No match found

