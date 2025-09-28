"""
Money normalization utilities for consistent amount/amount_minor handling.

Critical: This module fixes the amount/amount_minor consistency bug by ensuring
both fields are always written together with proper rounding and conversion.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def normalize_amount_fields(amount: Optional[float]) -> Tuple[Optional[float], Optional[int]]:
    """
    Normalize amount to consistent float and minor (cents) values.
    
    This function ensures:
    1. Proper decimal precision (2 decimal places)
    2. Consistent rounding (ROUND_HALF_UP)
    3. Accurate conversion to minor units (cents)
    4. Both fields always match: amount_minor = amount * 100
    
    Args:
        amount: The amount as a float
        
    Returns:
        Tuple of (normalized_amount, amount_minor)
        
    Example:
        >>> normalize_amount_fields(123.456)
        (123.46, 12346)
        >>> normalize_amount_fields(100.0)
        (100.0, 10000)
    """
    if amount is None:
        return None, None
    
    try:
        # Convert to Decimal for precise arithmetic
        decimal_amount = Decimal(str(amount)).quantize(
            Decimal("0.01"), 
            rounding=ROUND_HALF_UP
        )
        
        # Convert back to float for database storage
        normalized_amount = float(decimal_amount)
        
        # Calculate minor units (cents) with precise conversion
        amount_minor = int((decimal_amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
        
        # Validation: Ensure consistency
        expected_minor = int(normalized_amount * 100)
        if amount_minor != expected_minor:
            logger.warning(f"Minor unit calculation discrepancy: {amount_minor} vs {expected_minor}")
            amount_minor = expected_minor
        
        logger.debug(f"Normalized {amount} -> amount={normalized_amount}, minor={amount_minor}")
        return normalized_amount, amount_minor
        
    except (ValueError, TypeError, ArithmeticError) as e:
        logger.error(f"Error normalizing amount {amount}: {e}")
        raise ValueError(f"Invalid amount for normalization: {amount}") from e

def validate_amount_consistency(amount: Optional[float], amount_minor: Optional[int]) -> bool:
    """
    Validate that amount and amount_minor fields are consistent.
    
    Args:
        amount: The amount as float
        amount_minor: The amount in minor units (cents)
        
    Returns:
        True if consistent, False otherwise
    """
    if amount is None and amount_minor is None:
        return True
    
    if amount is None or amount_minor is None:
        return False
    
    try:
        normalized_amount, normalized_minor = normalize_amount_fields(amount)
        return normalized_minor == amount_minor
    except (ValueError, TypeError):
        return False

def fix_inconsistent_amounts(amount: Optional[float], amount_minor: Optional[int]) -> Tuple[Optional[float], Optional[int]]:
    """
    Fix inconsistent amount/amount_minor pairs by normalizing the amount field.
    
    This function prioritizes the amount field as the source of truth and
    recalculates amount_minor to match.
    
    Args:
        amount: The amount as float (source of truth)
        amount_minor: The potentially inconsistent minor amount
        
    Returns:
        Tuple of (corrected_amount, corrected_amount_minor)
    """
    logger.info(f"Fixing inconsistent amounts: {amount} vs {amount_minor}")
    normalized_amount, normalized_minor = normalize_amount_fields(amount)
    
    if amount_minor != normalized_minor:
        logger.warning(f"Corrected amount_minor: {amount_minor} -> {normalized_minor}")
    
    return normalized_amount, normalized_minor