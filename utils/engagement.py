"""
Engagement system for proactive finance coaching and user onboarding
Implements welcome prompts, learning loops, and habit-forming UX patterns
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Welcome prompt for new users
WELCOME_PROMPT = """👋 Hi {first_name}! I'm your personal finance assistant.
To guide you better, let's start with a few quick things:

1. What's your monthly income range? (pick one: < $500, $500–$1,000, $1,000–$2,500, > $2,500)
2. What's your biggest spending category? (food, rent, shopping, bills, other)
3. Do you want me to focus on saving tips, budgeting, or investment ideas first?"""

# Follow-up prompts for onboarding sequence
FOLLOWUP_PROMPTS = [
    "👍 Got it. How do you usually track your spending today? (apps, notebook, memory, nothing)",
    "💡 If I told you you're overspending in one area, would you prefer: a) warnings, b) savings tips, or c) detailed analysis?",
    "✨ What's your savings goal for the next 3 months? (eg: save $200, cut food spending, start emergency fund)"
]

# Rate limiting for AI responses per user
AI_LIMIT = 4  # max AI replies per window
WINDOW_SECONDS = 60  # rolling window

class EngagementEngine:
    """Handles user engagement, onboarding, and personalized interactions"""
    
    def __init__(self):
        self.user_requests = {}  # In-memory store for rate limiting
        
    def get_ai_prompt(self, user_data: Dict[str, Any], message: str, spend_data: Optional[Dict] = None) -> str:
        """Generate contextual AI prompt based on user state and data"""
        
        # New user onboarding
        if user_data.get('is_new', True):
            first_name = user_data.get('first_name', 'there')
            return WELCOME_PROMPT.format(first_name=first_name)
        
        # Onboarding sequence (steps 1-3)
        if not user_data.get('has_completed_onboarding', False):
            step = user_data.get('onboarding_step', 0)
            if step < len(FOLLOWUP_PROMPTS):
                return FOLLOWUP_PROMPTS[step]
            else:
                # Mark onboarding complete
                return "🎉 Great! You're all set up. Now I can give you personalized finance insights. What expense would you like to log or analyze today?"
        
        # Engaged user with spending data
        if spend_data:
            return self._make_engaging_response(user_data, spend_data)
        
        # Default prompt for established users
        first_name = user_data.get('first_name', 'there')
        return f"🤔 Can you tell me what expense you want me to log or analyze today, {first_name}?"
    
    def _make_engaging_response(self, user_data: Dict, spend_data: Dict) -> str:
        """Create engaging response with micro-insights and direct questions"""
        
        # Calculate percentages and insights
        total_spent = sum(spend_data.values())
        food_pct = int((spend_data.get('food', 0) / max(total_spent, 1)) * 100)
        
        response = f"""📊 Based on your last 7 days:
- Food spending: ${spend_data.get('food', 0):.0f}
- Shopping: ${spend_data.get('shopping', 0):.0f}
- Bills: ${spend_data.get('bills', 0):.0f}

🚦 Tip: Your food spending is {food_pct}% of recent expenses"""
        
        # Add personalized insight based on spending patterns
        if food_pct > 40:
            response += " — a bit high!\nWould you like me to suggest 3 practical cut-down tricks? (yes / no)"
        elif spend_data.get('shopping', 0) > spend_data.get('food', 0):
            response += ".\n💡 I notice more shopping than food expenses. Want tips to curb impulse buying? (yes / no)"
        else:
            response += ".\n✨ You're doing well! Want me to find areas where you can save even more? (yes / no)"
        
        return response
    
    def check_ai_rate_limit(self, user_id: str) -> Dict[str, Any]:
        """Check if user has exceeded AI interaction limit"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=WINDOW_SECONDS)
        
        # Clean old requests
        if user_id in self.user_requests:
            self.user_requests[user_id] = [
                timestamp for timestamp in self.user_requests[user_id] 
                if timestamp > cutoff
            ]
        else:
            self.user_requests[user_id] = []
        
        # Check limit
        current_count = len(self.user_requests[user_id])
        
        if current_count >= AI_LIMIT:
            return {
                'allowed': False,
                'fallback_message': "⏳ I can give 4 smart insights per minute. Let's continue in a moment! Meanwhile, want a quick money trivia? 🎲"
            }
        
        # Add current request
        self.user_requests[user_id].append(now)
        
        return {
            'allowed': True,
            'remaining': AI_LIMIT - current_count - 1
        }
    
    def get_habit_forming_response(self, user_data: Dict, interaction_count: int) -> Optional[str]:
        """Generate habit-forming prompts after certain interaction thresholds"""
        
        if interaction_count == 3:
            # Weekly challenge after 3 interactions
            return "Try not to spend on delivery food tomorrow. I'll check in and calculate what you saved. Deal? ✅/❌"
        
        elif interaction_count % 5 == 0:
            # Recurring engagement every 5 interactions
            return "Want me to track all your expenses this week and send a Friday report?"
        
        return None
    
    def get_conversation_ender(self, context: str = "general") -> str:
        """Generate engaging conversation endings with teasers"""
        
        endings = [
            "Want me to track all your expenses this week and send a Friday report?",
            "Should I remind you about your savings goal tomorrow?",
            "Ready for a spending challenge this week?",
            "Want me to analyze your spending patterns and find hidden savings?",
            "Shall I set up a weekly check-in to keep you on track?"
        ]
        
        if context == "spending":
            return endings[0]
        elif context == "savings":
            return endings[1]
        else:
            return endings[2]  # Default to challenge
    
    def update_user_onboarding(self, user_id: str, response: str, current_step: int) -> Dict[str, Any]:
        """Process onboarding response and update user state"""
        
        updates = {}
        
        if current_step == 0:  # Income range
            income_mapping = {
                '1': '< $500',
                '2': '$500–$1,000', 
                '3': '$1,000–$2,500',
                '4': '> $2,500'
            }
            
            for key, value in income_mapping.items():
                if key in response or value.lower() in response.lower():
                    updates['income_range'] = value
                    break
        
        elif current_step == 1:  # Biggest spending category
            categories = ['food', 'rent', 'shopping', 'bills', 'other']
            for category in categories:
                if category in response.lower():
                    updates['primary_category'] = category
                    break
        
        elif current_step == 2:  # Focus area
            focus_areas = ['saving', 'budgeting', 'investment']
            for area in focus_areas:
                if area in response.lower():
                    updates['focus_area'] = area
                    break
        
        # Advance to next step
        updates['onboarding_step'] = current_step + 1
        
        # Mark onboarding complete after step 2
        if current_step >= 2:
            updates['has_completed_onboarding'] = True
            updates['is_new'] = False
        
        return updates

# Global engagement engine instance
engagement_engine = EngagementEngine()