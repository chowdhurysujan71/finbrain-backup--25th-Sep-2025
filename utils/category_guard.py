"""
Server-side category normalization guard
Zero-risk protection against enum constraint violations
"""

from typing import Optional
import logging
from utils.validators import ExpenseValidator

logger = logging.getLogger(__name__)

def normalize_category_for_save(category: str) -> str:
    """
    Normalize category for database save - last line of defense
    
    Args:
        category: Raw category from client/AI/parsing
        
    Returns:
        Valid category or 'uncategorized' if unknown
    """
    if not category or not isinstance(category, str):
        logger.warning(f"Invalid category type: {type(category)}, normalizing to uncategorized")
        return 'uncategorized'
    
    # Normalize to lowercase for comparison
    category_clean = str(category).strip().lower()
    
    # Check if category is in valid set
    if category_clean in ExpenseValidator.VALID_CATEGORIES:
        return category_clean
    
    # Log the normalization for monitoring
    logger.info(f"Category normalization: '{category}' → 'uncategorized'")
    
    return 'uncategorized'