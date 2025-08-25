"""
Reply Templates for finbrain Corrections
Coach-style, natural, and helpful response formatting
"""

from decimal import Decimal
from typing import Optional

def format_correction_no_candidate_reply(amount: Decimal, currency: str, category: str) -> str:
    """
    Format reply when no correction candidate is found.
    
    Args:
        amount: Corrected amount
        currency: Currency code
        category: Expense category
        
    Returns:
        Formatted reply text
    """
    currency_symbol = {
        'BDT': '৳',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'INR': '₹'
    }.get(currency, currency)
    
    return (f"Got it! I didn't find a recent expense to correct, so I've logged "
            f"{currency_symbol}{amount} for {category} as a new expense. 📝")

def format_corrected_reply(old_amount: float, old_currency: str, new_amount: Decimal, 
                          new_currency: str, category: str, merchant: Optional[str] = None) -> str:
    """
    Format successful correction confirmation.
    
    Args:
        old_amount: Original amount
        old_currency: Original currency
        new_amount: Corrected amount
        new_currency: Corrected currency
        category: Expense category
        merchant: Merchant name if available
        
    Returns:
        Formatted confirmation text
    """
    old_symbol = {
        'BDT': '৳',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'INR': '₹'
    }.get(old_currency, old_currency)
    
    new_symbol = {
        'BDT': '৳',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'INR': '₹'
    }.get(new_currency, new_currency)
    
    merchant_part = f" at {merchant}" if merchant else ""
    
    return (f"✅ Corrected: {old_symbol}{old_amount} → {new_symbol}{new_amount} "
            f"for {category}{merchant_part}")

def format_correction_duplicate_reply() -> str:
    """
    Format reply for duplicate correction attempts.
    
    Returns:
        Formatted duplicate correction message
    """
    return "I've already processed that correction. Need to correct something else?"

def format_correction_error_reply() -> str:
    """
    Format generic error reply for correction failures.
    
    Returns:
        Formatted error message
    """
    return "Sorry, I couldn't process the correction. Please try logging the expense again."

def format_no_amount_in_correction_reply() -> str:
    """
    Format reply when correction message has no valid amount.
    
    Returns:
        Formatted no amount message
    """
    return "I didn't see a valid amount to correct to. Please try again with the new amount."

# Coach-tone variations for different correction scenarios
CORRECTION_SUCCESS_VARIATIONS = [
    "✅ Updated! {old_amount} → {new_amount} for {category}",
    "Corrected: {old_amount} → {new_amount} for {category} ✓",
    "Fixed! Changed from {old_amount} to {new_amount} for {category}",
    "Updated your {category} expense from {old_amount} to {new_amount} ✅"
]

CORRECTION_NO_CANDIDATE_VARIATIONS = [
    "No recent expense to correct, so logged {new_amount} for {category} as new 📝",
    "Couldn't find a recent match, created new {category} expense for {new_amount} ✓",
    "Added {new_amount} for {category} as a fresh entry since no recent one matched 📝"
]