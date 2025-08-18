"""
Normalized AI expense parsing with defensive handling
Fixes "function has no len()" errors through type safety
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def parse_expense(text: str) -> dict:
    """
    Return {'amount': float, 'category': str, 'note': Optional[str]}
    Raise ValueError on bad parse.
    """
    try:
        # Use existing expense parsing logic (simple implementation for now)
        # This will be enhanced with proper AI integration later
        result = {"amount": 0, "category": "Unknown", "note": text}
        
        # Basic parsing for common patterns
        import re
        pattern = r'(\d+(?:\.\d+)?)'
        amounts = re.findall(pattern, text)
        if amounts:
            result["amount"] = float(amounts[0])
        
        # Simple category detection
        if "coffee" in text.lower():
            result["category"] = "Food"
        elif "food" in text.lower() or "lunch" in text.lower():
            result["category"] = "Food"
        else:
            result["category"] = "Other"
        
        # Defensive: unwrap callables and enforce types
        if callable(result): 
            result = result()
        if not isinstance(result, dict):
            raise ValueError(f"AI parse returned {type(result)}")

        amt = result.get("amount")
        cat = result.get("category")
        note = result.get("note")

        # Unwrap any callable results
        if callable(amt): amt = amt()
        if callable(cat): cat = cat()
        if callable(note): note = note()

        # Validate amount
        if not isinstance(amt, (int, float, str)):
            raise ValueError("amount invalid")
        if isinstance(amt, str):
            # Crude but safe string to float conversion
            amt = float(amt.replace(",", " ").split()[0])

        # Validate category
        if not isinstance(cat, str) or not cat.strip():
            raise ValueError("category missing/invalid")

        # Clean note
        note = (note or "").strip() or None
        
        return {
            "amount": float(amt), 
            "category": cat.strip(), 
            "note": note
        }
        
    except Exception as e:
        logger.warning(f"AI expense parse failed: {e}")
        raise ValueError(f"AI parsing failed: {str(e)}")

def regex_parse(text: str) -> Optional[dict]:
    """
    Strict regex fallback parser
    Expects format: "spent X on Y" or "X on Y"
    """
    import re
    
    # Pattern: spent 200 on groceries OR 200 on groceries
    patterns = [
        r'^spent\s+(\d+(?:\.\d+)?)\s+on\s+([a-z ]+)$',
        r'^(\d+(?:\.\d+)?)\s+on\s+([a-z ]+)$',
        r'^([a-z ]+)\s+(\d+(?:\.\d+)?)$'  # coffee 50
    ]
    
    text_lower = text.lower().strip()
    
    for pattern in patterns:
        match = re.match(pattern, text_lower)
        if match:
            if pattern.endswith('([a-z ]+)$'):  # amount first
                amount_str, category = match.groups()
            else:  # category first (coffee 50)
                category, amount_str = match.groups()
            
            try:
                amount = float(amount_str)
                return {
                    "amount": amount,
                    "category": category.strip(),
                    "note": None
                }
            except ValueError:
                continue
    
    return None