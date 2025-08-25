"""
Normalized AI expense parsing with defensive handling
Fixes "function has no len()" errors through type safety
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def parse_expense(text: str, user_hash: str = None, check_ambiguity: bool = True) -> dict:
    """
    Enhanced expense parsing with conversational clarification support
    Returns {'amount': float, 'category': str, 'note': str|None, 'needs_clarification': bool, 'clarification_info': dict}
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
    
    parsed_result = {
        "amount": float(amt), 
        "category": cat.strip(), 
        "note": (note or "").strip() or None
    }
    
    # Add conversational clarification if enabled and user_hash provided
    if check_ambiguity and user_hash:
        try:
            from utils.expense_clarification import expense_clarification_handler
            
            # Extract main item from text for ambiguity checking
            item = _extract_main_item(text)
            
            if item:
                clarification_result = expense_clarification_handler.handle_expense_with_clarification(
                    user_hash, text, parsed_result["amount"], item, "temp_mid"
                )
                
                if clarification_result.get('needs_clarification'):
                    parsed_result['needs_clarification'] = True
                    parsed_result['clarification_info'] = clarification_result
                    parsed_result['temporary_category'] = parsed_result['category']  # Store original guess
                    parsed_result['category'] = 'pending_clarification'
                elif clarification_result.get('category'):
                    # Use learned or auto-detected category
                    parsed_result['category'] = clarification_result['category']
                    parsed_result['confidence_note'] = clarification_result.get('note', '')
                    
        except Exception as e:
            logger.warning(f"Clarification system error: {e}")
            # Continue with normal parsing if clarification fails
    
    return parsed_result

def _fallback_parse(text: str) -> dict:
    """Simple fallback parsing when AI is unavailable"""
    import re
    
    # Extract numbers (more flexible patterns)
    amounts = re.findall(r'(\d+(?:[.,]\d+)?)', text)
    if not amounts:
        # Instead of raising error, return None to let router handle gracefully
        raise ValueError("No amount found")
    
    # Take the first reasonable amount
    amount_str = amounts[0].replace(',', '.')
    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError("Invalid amount")
    except ValueError:
        raise ValueError("Invalid amount format")
    
    # Simple category detection with better patterns - ENHANCED FOR BENGALI FOOD
    text_lower = text.lower()
    if any(word in text_lower for word in ["coffee", "tea", "drink", "beverage", "starbucks", "cafe"]):
        category = "Food"
    elif any(word in text_lower for word in ["lunch", "dinner", "breakfast", "food", "meal", "restaurant", "eating"]):
        category = "Food"
    elif any(word in text_lower for word in ["khichuri", "rice", "dal", "curry", "biriyani", "roti", "naan", "chicken", "beef", "fish", "vegetable", "egg"]):
        category = "Food"
    elif any(word in text_lower for word in ["gas", "fuel", "petrol", "diesel"]):
        category = "Transport"
    elif any(word in text_lower for word in ["uber", "taxi", "bus", "parking", "transport", "travel"]):
        category = "Transport"
    elif any(word in text_lower for word in ["shopping", "store", "market", "buy", "purchase"]):
        category = "Shopping"
    elif any(word in text_lower for word in ["medicine", "doctor", "hospital", "pharmacy", "health"]):
        category = "Health"
    else:
        category = "Other"
    
    return {"amount": amount, "category": category, "note": None}

def _extract_main_item(text: str) -> Optional[str]:
    """Extract the main expense item from text for ambiguity checking"""
    import re
    
    # Remove common expense words and numbers
    text_clean = re.sub(r'\d+(?:\.\d+)?', '', text)  # Remove numbers
    words = text_clean.lower().split()
    
    # Remove common expense words - EXPANDED LIST
    skip_words = {'spent', 'paid', 'bought', 'for', 'on', 'the', 'a', 'an', 'at', 'in', 'with', 'by', 
                  'having', 'had', 'got', 'get', 'am', 'is', 'was', 'were', 'worth', 'taka', 'tk',
                  'cost', 'costs', 'costed', 'price', 'priced'}
    meaningful_words = [w for w in words if w not in skip_words and len(w) > 2]
    
    # Look for food items, product names, or nouns (usually later in sentence)
    for word in meaningful_words:
        # Skip common verbs and articles
        if word not in {'and', 'or', 'but', 'then', 'now', 'today', 'yesterday', 'this', 'that'}:
            return word
    
    return None

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

