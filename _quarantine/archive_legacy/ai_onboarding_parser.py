"""
AI-powered onboarding parser that understands natural language user responses
"""
import logging
from typing import Dict, Any, Optional
from ai_adapter_gemini import generate_with_schema

logger = logging.getLogger(__name__)

# Schema for AI parsing of onboarding responses
ONBOARDING_RESPONSE_SCHEMA = {
    "type": "object", 
    "properties": {
        "step": {"type": "integer", "description": "Which onboarding step this is (0=income, 1=categories, 2=focus)"},
        "income_range": {"type": "string", "enum": ["< $500", "$500–$1,000", "$1,000–$2,500", "> $2,500", "not_specified"], "description": "Parsed income range"},
        "categories": {"type": "array", "items": {"type": "string"}, "description": "List of spending categories mentioned"},
        "primary_category": {"type": "string", "description": "Main spending category"},
        "focus_area": {"type": "string", "enum": ["saving", "budgeting", "investment", "other"], "description": "User's preferred focus area"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "Confidence in parsing (0-1)"}
    },
    "required": ["step", "confidence"]
}

def ai_parse_onboarding_response(user_text: str, current_step: int) -> Dict[str, Any]:
    """
    Use AI to parse user onboarding responses intelligently
    
    Args:
        user_text: User's raw text input
        current_step: Current onboarding step (0=income, 1=categories, 2=focus)
    
    Returns:
        Parsed response with appropriate fields filled
    """
    
    # Create step-specific system prompt
    if current_step == 0:
        system_prompt = """Parse the user's income range response. They may respond with:
- Numbers like "1000-2500", "1", "2", "3", "4" 
- Text like "middle income", "low income", "high income"
- Formatted like "1. 1000-2500" or "option 2"
Map to: "< $500", "$500–$1,000", "$1,000–$2,500", "> $2,500" """
        
    elif current_step == 1:
        system_prompt = """Parse the user's spending categories. They may list:
- Multiple categories: "food, rent, shopping"
- Numbered format: "2. food, rent, shopping" 
- Single category: "food"
- Variations: "groceries" → "food", "housing" → "rent"
Extract all mentioned categories and identify the primary one."""
        
    elif current_step == 2:
        system_prompt = """Parse the user's focus area preference. They may say:
- "saving tips", "budgeting help", "investment advice"
- Single words: "saving", "budgeting", "investment"
- Descriptive: "help me save money", "track my budget"
Map to: "saving", "budgeting", "investment", or "other" """
    
    else:
        return {"step": current_step, "confidence": 0.0}
    
    # Create user prompt with context
    user_prompt = f"""User's response to onboarding step {current_step}: "{user_text}"
    
Current step context:
{system_prompt}

Parse this response and extract the relevant information."""
    
    try:
        # Use AI to parse the response
        result = generate_with_schema(
            user_text=user_prompt,
            system_prompt="You are an expert at parsing user responses during financial app onboarding. Extract structured data from natural language input.",
            response_schema=ONBOARDING_RESPONSE_SCHEMA
        )
        
        if result.get("ok") and "data" in result:
            parsed_data = result["data"]
            parsed_data["step"] = current_step  # Ensure step is set correctly
            
            logger.info(f"AI parsed onboarding step {current_step}: confidence={parsed_data.get('confidence', 0)}")
            return parsed_data
        else:
            logger.warning(f"AI parsing failed for step {current_step}: {result}")
            return {"step": current_step, "confidence": 0.0}
            
    except Exception as e:
        logger.error(f"Error in AI onboarding parsing: {e}")
        return {"step": current_step, "confidence": 0.0}

def convert_ai_parse_to_updates(ai_result: Dict[str, Any], current_step: int) -> Dict[str, Any]:
    """
    Convert AI parsing result to user database updates
    
    Args:
        ai_result: Result from ai_parse_onboarding_response
        current_step: Current onboarding step
    
    Returns:
        Dictionary of database field updates
    """
    updates = {}
    confidence = ai_result.get("confidence", 0)
    
    # Only apply updates if AI is confident
    if confidence < 0.7:
        logger.warning(f"Low confidence AI parse ({confidence}) for step {current_step}")
        # Fall back to basic parsing or keep current step
        updates['onboarding_step'] = current_step + 1  # Still advance step
        return updates
    
    if current_step == 0:  # Income step
        income_range = ai_result.get("income_range")
        if income_range and income_range != "not_specified":
            updates['income_range'] = income_range
        updates['onboarding_step'] = 1
        
    elif current_step == 1:  # Categories step
        categories = ai_result.get("categories", [])
        primary_category = ai_result.get("primary_category")
        
        if categories:
            if primary_category:
                updates['primary_category'] = primary_category
            else:
                updates['primary_category'] = categories[0]  # Use first as primary
            
            # Store all categories in preferences if multiple
            if len(categories) > 1:
                updates['preferences'] = {'spending_categories': categories}
        
        updates['onboarding_step'] = 2
        
    elif current_step == 2:  # Focus step
        focus_area = ai_result.get("focus_area", "saving")
        updates['focus_area'] = focus_area
        updates['has_completed_onboarding'] = True
        updates['is_new'] = False
        updates['onboarding_step'] = 0  # Reset
    
    return updates