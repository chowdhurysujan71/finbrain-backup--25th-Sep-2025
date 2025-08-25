"""
AI-powered FAQ classification system for finbrain
Handles natural language FAQ detection using existing Gemini integration
"""

import logging
from typing import Optional, Dict, Any
from utils.ai_adapter_v2 import production_ai_adapter

logger = logging.getLogger(__name__)

# FAQ category mappings to existing responses
FAQ_CATEGORIES = {
    "data_security": "is my financial data secure",
    "bank_integration": "can i connect my bank accounts", 
    "pricing": "how much does finbrain cost",
    "platform_features": "what is finbrain",
    "expense_tracking": "how does expense tracking work",
    "insights": "what kind of insights can i get",
    "getting_started": "how do i get started",
    "platforms": "what messaging platforms do you support"
}

def classify_faq_question(user_text: str) -> Optional[str]:
    """
    Use AI to classify if user question is FAQ-related
    
    Returns:
        FAQ category key or None if not FAQ-related
    """
    if not user_text or len(user_text.strip()) < 3:
        return None
        
    try:
        # Simple keyword-based pre-filter (fast path)
        text_lower = user_text.lower()
        
        # FIRST: Filter out expense-related queries (not FAQ)
        if any(phrase in text_lower for phrase in ["expenses this", "summary", "spent", "my expenses", "show me"]):
            return None
            
        # Quick keyword detection for obvious FAQ categories  
        if any(word in text_lower for word in ["data", "safe", "secure", "store", "privacy"]):
            return "data_security"
        elif any(word in text_lower for word in ["bank", "connect", "account", "link"]):
            return "bank_integration"
        elif any(phrase in text_lower for phrase in ["cost", "price", "free", "how much", "money", "pay"]):
            return "pricing"
        elif any(phrase in text_lower for phrase in ["what is finbrain", "what can finbrain", "what do you do", "who are you"]):
            return "platform_features"
        elif any(phrase in text_lower for phrase in ["how to track", "how to log", "log expense", "track expense"]):
            return "expense_tracking"
        elif any(word in text_lower for word in ["insight", "tip", "analysis", "recommend"]):
            return "insights"
        elif any(phrase in text_lower for phrase in ["get started", "how to start", "how do i begin"]):
            return "getting_started"
        elif any(word in text_lower for word in ["platform", "messenger", "app", "support"]):
            return "platforms"
        
        # If no keywords match, it's likely not FAQ
        return None
            
    except Exception as e:
        logger.error(f"[AI_FAQ] Classification error: {e}")
        return None

def get_faq_response(category: str) -> Optional[str]:
    """
    Get FAQ response for classified category
    
    Returns:
        FAQ response text or None if category not found
    """
    if category not in FAQ_CATEGORIES:
        return None
        
    try:
        from utils.faq_map import FAQ_JSON
        faq_key = FAQ_CATEGORIES[category]
        return FAQ_JSON["faq"].get(faq_key)
    except Exception as e:
        logger.error(f"[AI_FAQ] Error getting FAQ response: {e}")
        return None

def ai_enhanced_faq_detection(user_text: str) -> Optional[str]:
    """
    Complete AI-powered FAQ detection pipeline
    
    Returns:
        FAQ response text or None if not FAQ-related
    """
    try:
        # Step 1: Classify the question
        category = classify_faq_question(user_text)
        if not category:
            return None
            
        # Step 2: Get the appropriate response
        response = get_faq_response(category)
        if response:
            logger.info(f"[AI_FAQ] Generated response for category: {category}")
            
        return response
        
    except Exception as e:
        logger.error(f"[AI_FAQ] Complete pipeline error: {e}")
        return None