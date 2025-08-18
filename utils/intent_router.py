"""
Intent router: Detects user intent from message text
Priority order: SUMMARY/INSIGHT before LOG_EXPENSE to avoid false positives
"""
import re

# Intent detection patterns (order matters!)
RE_SUMMARY = re.compile(r'\b(summary|report|recap|how much.*spen[dt]|total (this|for) (week|month)|spent so far|what did i spend)\b', re.I)
RE_INSIGHT = re.compile(r'\b(insight|insights|tip|tips|advice|recommend|optimi[sz]e|suggestion)\b', re.I)
RE_LOG = re.compile(r'\b(spent|bought|paid|pay|\d+(?:\.\d{1,2})?\s*(bdt|tk|taka|usd)?)\b', re.I)
RE_UNDO = re.compile(r'\b(undo|remove|delete|cancel)\s*(last|recent|previous)?\b', re.I)

def detect_intent(text: str) -> str:
    """
    Detect user intent from message text.
    Returns: SUMMARY, INSIGHT, LOG_EXPENSE, UNDO, or UNKNOWN
    """
    t = (text or "").strip()
    
    # Check in priority order - commands before expense logging
    if RE_SUMMARY.search(t):
        return "SUMMARY"
    if RE_INSIGHT.search(t):
        return "INSIGHT"
    if RE_UNDO.search(t):
        return "UNDO"
    if RE_LOG.search(t):
        return "LOG_EXPENSE"
    
    return "UNKNOWN"