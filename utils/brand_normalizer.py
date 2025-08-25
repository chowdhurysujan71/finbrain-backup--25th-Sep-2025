"""
Brand Normalization Utility for finbrain
Ensures consistent lowercase branding in user-facing outputs without touching source code
"""
import re
import logging

logger = logging.getLogger(__name__)

def normalize_brand(text: str) -> str:
    """
    Normalize brand casing in user-facing text to 'finbrain'
    
    This is a safety-first approach that only affects outputs,
    never touching source code, database data, or AI prompts.
    
    Args:
        text: Input text that may contain various brand casings
        
    Returns:
        Text with normalized 'finbrain' branding
    """
    if not text or not isinstance(text, str):
        return text
    
    # Replace all common wrong casings with correct "finbrain"
    # But preserve context - don't change AI identity or internal references
    patterns = [
        (r'\bFinBrain(?=\s+(?:is|app|dashboard|admin|login))', 'finbrain'),  # UI contexts
        (r'\bFINBRAIN(?=\s+(?:SECURITY|DEPLOYMENT))', 'finbrain'),  # Documentation
        (r'\bFinbrain(?=\s+(?:expense|tracker))', 'finbrain'),  # Product references
    ]
    
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result

def normalize_ui_text(text: str) -> str:
    """
    Specifically for UI text normalization
    More aggressive since it's user-facing and not AI prompts
    """
    if not text or not isinstance(text, str):
        return text
    
    # Only normalize in UI contexts, never in AI conversation contexts
    ui_patterns = [
        (r'\b(FinBrain|Finbrain|FINBRAIN)(?=\s+(?:Dashboard|Admin|Login|Expense|Tracker))', 'finbrain'),
        (r'<title>[^<]*\b(FinBrain|Finbrain|FINBRAIN)\b[^<]*</title>', lambda m: m.group(0).replace(m.group(1), 'finbrain')),
    ]
    
    result = text
    for pattern, replacement in ui_patterns:
        if callable(replacement):
            result = re.sub(pattern, replacement, result)
        else:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result

# Safe areas for immediate normalization (lowest risk)
SAFE_NORMALIZATION_AREAS = [
    'documentation',
    'admin_interfaces', 
    'internal_logs',
    'code_comments'
]

# Areas to NEVER normalize (preserve AI identity and external integrations)
PRESERVE_AREAS = [
    'ai_prompts',
    'facebook_config',
    'database_data',
    'webhook_endpoints',
    'faq_responses'  # Users expect consistent AI identity
]