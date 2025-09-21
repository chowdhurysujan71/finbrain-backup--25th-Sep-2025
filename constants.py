"""
finbrain Constants - Single Source of Truth
Centralized constants to prevent hardcoded values and ensure consistency
"""

# =================================================================
# EXPENSE SOURCE VALIDATION - WEB-ONLY ARCHITECTURE
# =================================================================

# Valid sources for expense writes (web-only architecture)
ALLOWED_SOURCES = {'chat'}

# Legacy source mapping for read-side analytics only
# Maps old source values to current canonical source for reporting
LEGACY_SOURCE_MAPPING = {
    'messenger': 'chat',  # Deprecated - Messenger integration removed
    'form': 'chat',       # Deprecated - Consolidated to chat interface  
    'web': 'chat',        # Legacy - Now unified as chat
    'pwa': 'chat',        # Legacy - Progressive Web App now chat
    'api': 'chat',        # Legacy - API calls now via chat interface
    'chat': 'chat'        # Current - Web-only chat interface
}

def validate_expense_source(source: str) -> None:
    """
    Validate expense source against allowed sources
    
    Args:
        source: Source identifier to validate
        
    Raises:
        ValueError: If source is not in ALLOWED_SOURCES
    """
    if source not in ALLOWED_SOURCES:
        allowed_list = ', '.join(sorted(ALLOWED_SOURCES))
        raise ValueError(
            f"Invalid source '{source}'. Web-only architecture requires source: {allowed_list}"
        )

def normalize_source_for_analytics(source: str) -> str:
    """
    Normalize legacy source values for read-side analytics
    
    Args:
        source: Original source value from database
        
    Returns:
        Normalized source value for analytics/reporting
    """
    return LEGACY_SOURCE_MAPPING.get(source, 'chat')

# =================================================================
# OTHER CONSTANTS
# =================================================================

# Currency constants
DEFAULT_CURRENCY = 'BDT'
SUPPORTED_CURRENCIES = {'BDT', 'USD', 'EUR'}

# Amount validation constants  
MIN_AMOUNT = 0.01
MAX_AMOUNT = 99999999.99