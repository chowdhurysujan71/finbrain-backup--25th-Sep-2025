"""
Enhanced money pattern recognition with Bengali support
Handles currency symbols, Bengali "টাকা" word, and both orderings
"""
import re

# Currency patterns - symbols and Bengali word
CURRENCY_BEFORE = r"(?:৳|tk|bdt|taka|টাকা)"

# Number patterns - supports comma-separated thousands and decimals
NUM = r"(?:[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"

# Money regex - handles both currency-before-number and number-before-currency
RE_MONEY = re.compile(
    rf"(?:{CURRENCY_BEFORE})\s*({NUM})|({NUM})\s*(?:{CURRENCY_BEFORE})",
    flags=re.IGNORECASE
)

def extract_money_mentions(text: str) -> list:
    """
    Extract all money mentions from text
    
    Args:
        text: Input text (should be normalized with Bengali digits converted)
        
    Returns:
        List of money mention strings
    """
    return [match.group(0) for match in RE_MONEY.finditer(text)]

def has_money_mention(text: str) -> bool:
    """
    Check if text contains any money mentions
    
    Args:
        text: Input text
        
    Returns:
        True if money patterns found
    """
    return bool(RE_MONEY.search(text))