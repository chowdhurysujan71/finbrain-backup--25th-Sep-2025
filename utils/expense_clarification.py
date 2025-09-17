"""
FinBrain Conversational Clarification System
Handles natural conversation flow for ambiguous expense categorization
"""

import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from utils.expense_ambiguity import ambiguity_detector
from utils.expense_learning import user_learning_system
from utils.brand_normalizer import normalize

logger = logging.getLogger(__name__)

# Temporary storage for pending clarifications (in production, use Redis)
_pending_clarifications = {}

class ExpenseClarificationHandler:
    """Handles conversational clarification for ambiguous expenses"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ExpenseClarificationHandler")
    
    def handle_expense_with_clarification(self, user_hash: str, original_text: str, 
                                        amount: float, item: str, mid: str) -> Dict[str, Any]:
        """
        Main handler for expense that might need clarification
        
        Args:
            user_hash: User's PSID hash
            original_text: Original message text
            amount: Expense amount
            item: The main expense item
            mid: Message ID for tracking
            
        Returns:
            Dict with response and any clarification needed
        """
        try:
            # First check if user has a learned preference for this item
            user_preference = user_learning_system.get_user_preference(user_hash, item)
            if user_preference:
                # User has taught us their preference - use it directly
                return {
                    'needs_clarification': False,
                    'category': user_preference['category'],
                    'confidence': 'learned',
                    'note': f"Used your preference: {item} → {user_preference['category']}"
                }
            
            # Check for ambiguity
            ambiguity_result = ambiguity_detector.detect_ambiguity(
                item, amount, original_text
            )
            
            if not ambiguity_result['is_ambiguous']:
                # Not ambiguous - use the suggested category
                return {
                    'needs_clarification': False,
                    'category': ambiguity_result.get('auto_category', 'other'),
                    'confidence': ambiguity_result.get('confidence', 50),
                    'note': 'Auto-categorized'
                }
            
            # Ambiguous item - need clarification
            return self._initiate_clarification(
                user_hash, original_text, amount, item, mid, ambiguity_result
            )
            
        except Exception as e:
            self.logger.error(f"Error handling expense clarification: {e}")
            return {
                'needs_clarification': False,
                'category': 'other',
                'confidence': 0,
                'note': 'Error in clarification - defaulted to Other'
            }
    
    def _initiate_clarification(self, user_hash: str, original_text: str, 
                              amount: float, item: str, mid: str, 
                              ambiguity_result: Dict) -> Dict[str, Any]:
        """Initiate clarification conversation with user"""
        
        # Store pending clarification
        clarification_id = f"{user_hash}_{mid}_{int(datetime.utcnow().timestamp())}"
        
        _pending_clarifications[clarification_id] = {
            'user_hash': user_hash,
            'original_text': original_text,
            'amount': amount,
            'item': item,
            'mid': mid,
            'options': ambiguity_result['options'],
            'created_at': datetime.utcnow(),
            'expires_at': datetime.utcnow() + timedelta(minutes=10)
        }
        
        # Generate conversational clarification message
        clarification_message = self._generate_clarification_message(
            item, amount, ambiguity_result['options']
        )
        
        return {
            'needs_clarification': True,
            'clarification_id': clarification_id,
            'message': clarification_message,
            'options': ambiguity_result['options'],
            'temporary_category': 'pending_clarification'
        }
    
    def _generate_clarification_message(self, item: str, amount: float, 
                                      options: List[Dict]) -> str:
        """Generate natural conversational clarification message"""
        
        # Create options text
        option_texts = []
        for i, option in enumerate(options[:3], 1):  # Show top 3 options
            example = option.get('example', '')
            if example and example != option['display_name']:
                option_texts.append(f"{i}. {option['display_name']} ({example})")
            else:
                option_texts.append(f"{i}. {option['display_name']}")
        
        # Add "something else" option
        option_texts.append(f"{len(option_texts) + 1}. Something else")
        
        options_formatted = "\n".join(option_texts)
        
        message = f"""Got it! I logged ৳{amount:.0f} for your {item}. 

Quick question - what type of {item} was this?

{options_formatted}

Just reply with the number or tell me what it was!"""
        
        return normalize(message)
    
    def handle_clarification_response(self, user_hash: str, response_text: str) -> Optional[Dict[str, Any]]:
        """
        Handle user's response to a clarification question
        
        Args:
            user_hash: User's PSID hash
            response_text: User's response
            
        Returns:
            Dict with clarification result or None if no pending clarification
        """
        try:
            # Find pending clarification for this user
            pending = self._find_pending_clarification(user_hash)
            if not pending:
                return None
            
            clarification_id = pending['clarification_id']
            clarification_data = pending['data']
            
            # Parse user's response
            chosen_category = self._parse_clarification_response(
                response_text, clarification_data['options']
            )
            
            if not chosen_category:
                # User's response wasn't clear - ask again
                return {
                    'success': False,
                    'message': "I didn't catch that. Please reply with a number (1, 2, 3...) or tell me what category it should be!",
                    'retry': True
                }
            
            # Learn the user's preference
            user_learning_system.learn_user_preference(
                user_hash, 
                clarification_data['item'], 
                chosen_category,
                {
                    'amount': clarification_data['amount'],
                    'original_text': clarification_data['original_text']
                }
            )
            
            # Record the interaction
            options_shown = [opt['category'] for opt in clarification_data['options']]
            user_learning_system.record_clarification_interaction(
                user_hash, clarification_data['item'], options_shown, chosen_category
            )
            
            # Clean up pending clarification
            del _pending_clarifications[clarification_id]
            
            # CRITICAL FIX: Actually save the expense to database after clarification
            try:
                from backend_assistant import add_expense
                from datetime import datetime
                
                # Extract expense data from clarification
                amount = clarification_data['amount']
                item = clarification_data['item']
                
                # Call add_expense to persist the clarified expense
                expense_result = add_expense(
                    user_id=user_hash,
                    amount_minor=int(amount * 100),  # Convert to minor units (cents)
                    currency="BDT",
                    category=chosen_category,
                    description=f"{item} for ৳{amount}",
                    source="chat",
                    message_id=clarification_data.get('mid')
                )
                
                self.logger.info(f"Saved clarified expense: ৳{amount} for {item} as {chosen_category}")
                
            except Exception as e:
                self.logger.error(f"Failed to save clarified expense: {e}")
                # Still return success since clarification was handled, but log the error
            
            # Generate confirmation message
            confirmation_message = self._generate_confirmation_message(
                clarification_data['item'], clarification_data['amount'], chosen_category
            )
            
            return {
                'success': True,
                'category': chosen_category,
                'message': confirmation_message,
                'original_expense': clarification_data,
                'learned': True,
                'expense_saved': True
            }
            
        except Exception as e:
            self.logger.error(f"Error handling clarification response: {e}")
            return {
                'success': False,
                'message': "Sorry, something went wrong. Let's try logging the expense again!",
                'retry': True
            }
    
    def _find_pending_clarification(self, user_hash: str) -> Optional[Dict[str, Any]]:
        """Find pending clarification for user"""
        now = datetime.utcnow()
        
        # Clean up expired clarifications
        expired_keys = []
        for key, data in _pending_clarifications.items():
            if data['expires_at'] < now:
                expired_keys.append(key)
        
        for key in expired_keys:
            del _pending_clarifications[key]
        
        # Find user's pending clarification
        for clarification_id, data in _pending_clarifications.items():
            if data['user_hash'] == user_hash and data['expires_at'] > now:
                return {
                    'clarification_id': clarification_id,
                    'data': data
                }
        
        return None
    
    def _parse_clarification_response(self, response: str, options: List[Dict]) -> Optional[str]:
        """Parse user's clarification response"""
        response_clean = response.lower().strip()
        
        # Try to parse as number
        try:
            choice_num = int(response_clean)
            if 1 <= choice_num <= len(options):
                return options[choice_num - 1]['category']
        except ValueError:
            pass
        
        # Try to match keywords
        for option in options:
            category = option['category']
            display_name = option['display_name'].lower()
            
            if category in response_clean or display_name in response_clean:
                return category
            
            # Check for partial matches
            if 'electronics' in response_clean or 'tech' in response_clean or 'computer' in response_clean:
                if category == 'electronics':
                    return category
            elif 'food' in response_clean or 'eat' in response_clean or 'drink' in response_clean:
                if category == 'food':
                    return category
            elif 'pet' in response_clean or 'animal' in response_clean:
                if category == 'pet':
                    return category
            elif 'medicine' in response_clean or 'health' in response_clean or 'pharmacy' in response_clean:
                if category == 'health':
                    return category
        
        # Try common category keywords
        category_keywords = {
            'electronics': ['electronics', 'tech', 'computer', 'device', 'gadget'],
            'food': ['food', 'eat', 'drink', 'meal', 'snack'],
            'transport': ['transport', 'travel', 'car', 'bus', 'taxi'],
            'shopping': ['shopping', 'store', 'buy', 'purchase'],
            'health': ['health', 'medicine', 'doctor', 'pharmacy'],
            'entertainment': ['entertainment', 'fun', 'movie', 'game']
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in response_clean for keyword in keywords):
                return category
        
        return None
    
    def _generate_confirmation_message(self, item: str, amount: float, category: str) -> str:
        """Generate confirmation message after clarification"""
        
        friendly_category = self._get_friendly_category_name(category)
        
        message = f"Perfect! ✅ Updated: ৳{amount:.0f} for {friendly_category}. I'll remember that {item} means {friendly_category} for you!"
        
        return normalize(message)
    
    def _get_friendly_category_name(self, category: str) -> str:
        """Get user-friendly category name"""
        friendly_names = {
            'electronics': 'Electronics',
            'food': 'Food',
            'pet': 'Pet Care',
            'health': 'Health',
            'bills': 'Bills',
            'entertainment': 'Entertainment',
            'shopping': 'Shopping',
            'transport': 'Transportation',
            'other': 'Other'
        }
        return friendly_names.get(category, category.title())


# Initialize the global clarification handler
expense_clarification_handler = ExpenseClarificationHandler()