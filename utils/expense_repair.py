"""
Expense Repair Utilities with Circuit Breaker Pattern
Provides safe expense detection and repair for AI misclassifications
"""

import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Expense detection patterns
EXPENSE_HINTS = re.compile(r"\b(spent|paid|buy|bought|purchase|purchased|cost|bill)\b", re.I)
AMOUNT_RE = re.compile(
    r"(?:৳|tk|taka)\s*([0-9][0-9,\.]*)|\b([0-9][0-9,\.]*)\s*(?:taka|tk|৳)\b",
    re.I
)

# Category normalization
ALLOWED_CATEGORIES = {"food", "transport", "bills", "shopping", "uncategorized"}
CATEGORY_SYNONYMS = {
    "other": "uncategorized", 
    "misc": "uncategorized",
    "miscellaneous": "uncategorized",
    "grocery": "food",
    "groceries": "food",
    "dinner": "food",
    "lunch": "food",
    "breakfast": "food",
    "uber": "transport",
    "taxi": "transport",
    "ride": "transport",
    "bus": "transport",
    "utilities": "bills",
    "utility": "bills",
    "clothes": "shopping",
    "clothing": "shopping"
}

def looks_like_expense(text: str) -> bool:
    """
    Detect if text looks like an expense even if AI missed it
    
    Args:
        text: Input text to analyze
        
    Returns:
        True if text contains expense patterns
    """
    if not text:
        return False
    
    return bool(EXPENSE_HINTS.search(text) and AMOUNT_RE.search(text))

def extract_amount_minor(text: str) -> Optional[int]:
    """
    Extract amount in minor units (paisa/cents) from text
    
    Args:
        text: Input text containing amount
        
    Returns:
        Amount in minor units (e.g., 30000 for 300 taka) or None
    """
    if not text:
        return None
    
    match = AMOUNT_RE.search(text)
    if not match:
        return None
    
    # Get the first non-None group
    raw_amount = next((g for g in match.groups() if g), None)
    if not raw_amount:
        return None
    
    try:
        # Clean and convert to minor units
        cleaned = raw_amount.replace(",", "")
        amount_float = float(cleaned)
        return int(round(amount_float * 100))  # Convert to minor units
    except (ValueError, TypeError):
        logger.warning("amount_extraction_failed", raw=raw_amount, text=text[:50])
        return None

def guess_category(text: str) -> str:
    """
    Guess expense category from text content
    
    Args:
        text: Input text to analyze
        
    Returns:
        Guessed category (always one of ALLOWED_CATEGORIES)
    """
    if not text:
        return "uncategorized"
    
    text_lower = text.lower()
    
    # Food keywords
    if any(keyword in text_lower for keyword in ["dinner", "lunch", "breakfast", "meal", "restaurant", "food", "coffee", "tea"]):
        return "food"
    
    # Transport keywords  
    if any(keyword in text_lower for keyword in ["uber", "taxi", "bus", "rickshaw", "train", "ride", "transport"]):
        return "transport"
    
    # Bills keywords
    if any(keyword in text_lower for keyword in ["bill", "utility", "electric", "gas", "water", "internet", "phone"]):
        return "bills"
    
    # Shopping keywords
    if any(keyword in text_lower for keyword in ["buy", "bought", "shopping", "store", "mall", "purchase", "shop"]):
        return "shopping"
    
    return "uncategorized"

def normalize_category(raw_category: str) -> str:
    """
    Import canonical normalize_category from backend_assistant
    Ensures single source of truth for category normalization
    """
    from backend_assistant import normalize_category as canonical_normalize_category
    return canonical_normalize_category(raw_category)

def repair_expense_with_fallback(
    text: str, 
    original_intent: str, 
    original_amount: Optional[int], 
    original_category: Optional[str]
) -> Tuple[str, Optional[int], str]:
    """
    Circuit-breaker: safely repair expense misclassification
    
    Never throws; logs and returns original classification on error.
    Only switches to add_expense if we can safely extract an amount.
    
    Args:
        text: Original user message
        original_intent: AI's intent classification
        original_amount: AI's extracted amount (minor units)
        original_category: AI's category classification
        
    Returns:
        Tuple of (intent, amount_minor, normalized_category)
    """
    try:
        # Check if repair is needed and possible
        if original_intent != "add_expense" and looks_like_expense(text):
            logger.info("repair_attempt_started", text_hash=hash(text), original_intent=original_intent)
            
            # Try to extract amount if missing
            repaired_amount = original_amount or extract_amount_minor(text)
            
            if repaired_amount:
                # We can repair - extract/guess category
                if original_category:
                    repaired_category = normalize_category(original_category)
                else:
                    repaired_category = normalize_category(guess_category(text))
                
                logger.info("repair_success", 
                           original_intent=original_intent,
                           repaired_amount=repaired_amount, 
                           repaired_category=repaired_category)
                
                return "add_expense", repaired_amount, repaired_category
            else:
                # No amount detected - bypass repair
                logger.info("repair_bypass", reason="no_amount_detected")
                return original_intent, original_amount, normalize_category(original_category)
        
        # No repair needed - just normalize category
        return original_intent, original_amount, normalize_category(original_category)
        
    except Exception as e:
        # Circuit breaker - never fail, log and return original
        logger.warning("repair_failed", error=str(e), text=(text or "")[:80])
        return original_intent, original_amount, normalize_category(original_category)