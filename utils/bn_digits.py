"""
Bengali digit normalization utilities
Converts Bengali numerals to ASCII for consistent pattern matching
"""

# Bengali to English digit translation table
BN2EN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

def to_en_digits(s: str) -> str:
    """
    Convert Bengali digits to English digits
    
    Args:
        s: Input string that may contain Bengali digits
        
    Returns:
        String with Bengali digits converted to ASCII
    """
    if not isinstance(s, str):
        return str(s)
    return s.translate(BN2EN)