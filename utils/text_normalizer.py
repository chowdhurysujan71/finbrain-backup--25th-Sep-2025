"""
Text normalization utilities for consistent processing
Handles Unicode normalization, zero-width characters, and casefold for i18n
"""
from __future__ import annotations
import unicodedata
import re

# Zero-width characters: ZWSP, ZWNJ, ZWJ, BOM
_ZERO_WIDTH_CHARS = re.compile(r"[\u200B-\u200D\uFEFF]")

def normalize_for_processing(text: str) -> str:
    """
    Normalize text for consistent signal extraction and processing
    
    Args:
        text: Raw input text
        
    Returns:
        Normalized text ready for pattern matching
    """
    if not isinstance(text, str):
        return ""
    
    # 1. Unicode canonical form (handles composed characters)
    normalized = unicodedata.normalize("NFKC", text)
    
    # 2. Convert Bengali numerals to ASCII using proper utility
    from utils.bn_digits import to_en_digits
    normalized = to_en_digits(normalized)
    
    # 3. Remove zero-width characters that can break pattern matching
    normalized = _ZERO_WIDTH_CHARS.sub("", normalized)
    
    # 4. Case folding for international text (better than lower())
    normalized = normalized.casefold()
    
    # 5. Collapse multiple whitespace to single spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()
    
    return normalized