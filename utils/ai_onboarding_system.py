"""
Complete AI-driven onboarding system with flexible data handling
"""
import logging
import json
from typing import Dict, Any, Optional, Tuple
from ai_adapter_gemini import generate_with_schema

logger = logging.getLogger(__name__)

# AI-driven onboarding schema - flexible and adaptive
ONBOARDING_SCHEMA = {
    "type": "object",
    "properties": {
        "user_state": {
            "type": "string", 
            "enum": ["new", "collecting_income", "collecting_categories", "collecting_focus", "completed"],
            "description": "Current onboarding state"
        },
        "next_question": {
            "type": "string",
            "description": "Next question to ask the user"
        },
        "extracted_data": {
            "type": "object",
            "properties": {
                "income_range": {"type": "string"},
                "spending_categories": {"type": "array", "items": {"type": "string"}},
                "primary_category": {"type": "string"},
                "focus_area": {"type": "string"},
                "first_name": {"type": "string"},
                "additional_info": {"type": "object"}
            }
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "should_complete": {"type": "boolean", "description": "Whether onboarding should be marked complete"}
    },
    "required": ["user_state", "confidence"]
}

class AIOnboardingSystem:
    """Complete AI-driven onboarding system"""
    
    def __init__(self):
        self.welcome_prompt = """👋 Hi there! I'm your personal finance assistant. To guide you better, let's start with a few quick things:

1. What's your monthly income range?
2. What are your biggest spending categories?
3. What would you like to focus on?

Just tell me in your own words - I'll understand!"""

    def process_user_response(self, user_text: str, current_user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Process user response using AI to understand intent and extract data
        Returns: (response_text, updated_user_data)
        """
        
        # Check if user is on consent step (step 0) - handle privacy consent first
        current_step = current_user_data.get('onboarding_step', 0)
        if current_step == 0:
            # Check if user has already given consent
            if not current_user_data.get('privacy_consent_given', False):
                return self._handle_consent_step(user_text, current_user_data)
        
        # Build context about user's current state
        context = self._build_user_context(current_user_data)
        
        # Create AI prompt
        system_prompt = """You are an intelligent onboarding assistant for a finance app. 
        
Your job is to:
1. Understand what the user is telling you (income, spending, preferences)
2. Decide what state they should be in (new, collecting_income, etc.)
3. Ask the next appropriate question to complete their profile
4. Extract any data they've provided

Be conversational and flexible. Users might give multiple pieces of info at once or in various formats."""
        
        user_prompt = f"""Current user context: {context}
        
User's message: "{user_text}"

Analyze this message and determine:
- What information they've provided
- What their current onboarding state should be
- What question to ask next (if any)
- Whether onboarding should be completed"""

        try:
            # Use AI to process the response
            result = generate_with_schema(
                user_text=user_prompt,
                system_prompt=system_prompt,
                response_schema=ONBOARDING_SCHEMA
            )
            
            if result.get("ok") and "data" in result:
                ai_response = result["data"]
                
                # Ensure required fields are present
                if 'user_state' not in ai_response:
                    ai_response['user_state'] = 'collecting_income'
                if 'confidence' not in ai_response:
                    ai_response['confidence'] = 0.8
                
                return self._handle_ai_response(ai_response, current_user_data)
            else:
                logger.warning(f"AI onboarding failed: {result}")
                return self._fallback_response(user_text, current_user_data)
                
        except Exception as e:
            logger.error(f"Error in AI onboarding: {e}")
            return self._fallback_response(user_text, current_user_data)
    
    def _build_user_context(self, user_data: Dict[str, Any]) -> str:
        """Build context string about user's current state"""
        context_parts = []
        
        if user_data.get('first_name'):
            context_parts.append(f"Name: {user_data['first_name']}")
        
        if user_data.get('income_range'):
            context_parts.append(f"Income: {user_data['income_range']}")
        
        if user_data.get('primary_category'):
            context_parts.append(f"Primary spending: {user_data['primary_category']}")
        
        if user_data.get('focus_area'):
            context_parts.append(f"Focus: {user_data['focus_area']}")
        
        onboarding_step = user_data.get('onboarding_step', 0)
        is_new = user_data.get('is_new', True)
        completed = user_data.get('has_completed_onboarding', False)
        
        context_parts.append(f"Step: {onboarding_step}, New: {is_new}, Completed: {completed}")
        
        return "; ".join(context_parts) if context_parts else "New user, no data collected"
    
    def _handle_ai_response(self, ai_response: Dict[str, Any], current_user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle AI response and update user data"""
        
        user_state = ai_response.get("user_state", "new")
        next_question = ai_response.get("next_question", "")
        extracted_data = ai_response.get("extracted_data", {})
        should_complete = ai_response.get("should_complete", False)
        confidence = ai_response.get("confidence", 0)
        
        # Update user data with extracted information
        updated_data = current_user_data.copy()
        
        # Apply extracted data
        for key, value in extracted_data.items():
            if value and value != "":
                if key == "additional_info" and isinstance(value, dict):
                    # Merge additional info
                    current_additional = updated_data.get('additional_info', {})
                    current_additional.update(value)
                    updated_data['additional_info'] = current_additional
                else:
                    updated_data[key] = value
        
        # Update state based on AI decision
        if should_complete or user_state == "completed":
            updated_data['has_completed_onboarding'] = True
            updated_data['is_new'] = False
            updated_data['onboarding_step'] = 0
            response_text = "🎉 Perfect! You're all set up. I can now give you personalized finance insights. What expense would you like to log or analyze today?"
        else:
            # Map AI state to internal step (consent = 0, then shifted +1)
            state_to_step = {
                "new": 0,
                "collecting_consent": 0,
                "collecting_income": 1,
                "collecting_categories": 2,
                "collecting_focus": 3
            }
            updated_data['onboarding_step'] = state_to_step.get(user_state, 0)
            updated_data['has_completed_onboarding'] = False
            
            # Use AI-generated next question or fallback
            response_text = next_question or self._get_fallback_question(user_state)
        
        logger.info(f"AI onboarding: state={user_state}, confidence={confidence}, completed={should_complete}")
        
        return response_text, updated_data
    
    def _detect_consent(self, user_text: str) -> bool:
        """Detect if user has given consent"""
        consent_patterns = [
            "i agree", "i accept", "yes", "okay", "ok", "sure", 
            "agreed", "accept", "consent", "i consent", "yes i agree"
        ]
        text_lower = user_text.lower().strip()
        return any(pattern in text_lower for pattern in consent_patterns)
    
    def _handle_consent_step(self, user_text: str, current_user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Handle privacy consent step specifically"""
        from datetime import datetime
        
        if self._detect_consent(user_text):
            # User has given consent
            updated_data = current_user_data.copy()
            updated_data['privacy_consent_given'] = True
            updated_data['privacy_consent_at'] = datetime.utcnow()
            updated_data['terms_accepted'] = True
            updated_data['terms_accepted_at'] = datetime.utcnow()
            updated_data['onboarding_step'] = 1  # Move to income step
            
            response = "✅ Thank you! Now let's set up your financial profile.\n\nWhat's your monthly income range? (e.g., 1000-2500)"
            return response, updated_data
        else:
            # User hasn't given consent, stay on consent step
            response = (
                "⚠️ To continue, you need to accept our Privacy Policy and Terms of Service.\n\n"
                "📋 Privacy Policy: https://www.finbrain.app/privacy-policy\n"
                "📜 Terms of Service: https://www.finbrain.app/terms-of-service\n\n"
                "Please reply \"I agree\" to continue."
            )
            return response, current_user_data

    def _get_fallback_question(self, user_state: str) -> str:
        """Get fallback question based on state"""
        questions = {
            "new": (
                "🔒 Welcome to finbrain! Before we start, please review:\n\n"
                "📋 Privacy Policy: https://www.finbrain.app/privacy-policy\n"
                "📜 Terms of Service: https://www.finbrain.app/terms-of-service\n\n"
                "Reply \"I agree\" to continue with your financial tracking setup."
            ),
            "collecting_consent": (
                "🔒 To continue, please accept our terms:\n\n"
                "📋 Privacy Policy: https://www.finbrain.app/privacy-policy\n"
                "📜 Terms of Service: https://www.finbrain.app/terms-of-service\n\n"
                "Reply \"I agree\" to continue."
            ),
            "collecting_income": "What's your monthly income range? (e.g., 1000-2500)",
            "collecting_categories": "What are your biggest spending categories? (e.g., food, rent, shopping)",
            "collecting_focus": "What would you like to focus on? (saving, budgeting, or investment tips)"
        }
        return questions.get(user_state, "Tell me about your finances!")
    
    def _fallback_response(self, user_text: str, current_user_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Fallback when AI fails"""
        step = current_user_data.get('onboarding_step', 0)
        updated_data = current_user_data.copy()
        
        # Simple progression with consent step (0=consent, 1=income, 2=categories, 3=focus)
        if step < 3:
            updated_data['onboarding_step'] = step + 1
            # Map step to appropriate question
            if step == 0:  # After consent, ask for income
                response = self._get_fallback_question("collecting_income")
            elif step == 1:  # After income, ask for categories  
                response = self._get_fallback_question("collecting_categories")
            else:  # After categories, ask for focus
                response = self._get_fallback_question("collecting_focus")
        else:
            updated_data['has_completed_onboarding'] = True
            updated_data['is_new'] = False
            updated_data['onboarding_step'] = 0
            response = "Thanks! You're all set up. What would you like to track today?"
        
        return response, updated_data

# Global instance
ai_onboarding_system = AIOnboardingSystem()