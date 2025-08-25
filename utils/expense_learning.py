"""
FinBrain User Learning System
Stores and retrieves user-specific category preferences and patterns
"""

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from app import db
from models import User

logger = logging.getLogger(__name__)

class UserLearningSystem:
    """Manages user-specific learning and preferences for expense categorization"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.UserLearningSystem")
    
    def learn_user_preference(self, user_hash: str, item: str, chosen_category: str, 
                            context: Dict[str, Any] = None) -> bool:
        """
        Store a user's category preference for a specific item
        
        Args:
            user_hash: User's PSID hash
            item: The expense item (e.g., "mouse")
            chosen_category: The category the user selected
            context: Additional context (amount, keywords, etc.)
            
        Returns:
            True if successfully stored, False otherwise
        """
        try:
            user = self._get_or_create_user(user_hash)
            
            # Get existing preferences
            preferences = user.preferences or {}
            
            # Initialize category mappings if not exists
            if 'category_mappings' not in preferences:
                preferences['category_mappings'] = {}
            
            # Store the user's preference
            item_key = item.lower().strip()
            preferences['category_mappings'][item_key] = {
                'category': chosen_category,
                'learned_at': datetime.utcnow().isoformat(),
                'context': context or {},
                'confidence': 100  # User explicitly chose this
            }
            
            # Also update learning stats
            if 'learning_stats' not in preferences:
                preferences['learning_stats'] = {}
            
            preferences['learning_stats'][f"{item_key}_corrections"] = \
                preferences['learning_stats'].get(f"{item_key}_corrections", 0) + 1
            
            # Save to database
            user.preferences = preferences
            db.session.commit()
            
            self.logger.info(f"Learned preference: {item} → {chosen_category} for user {user_hash[:8]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to learn user preference: {e}")
            db.session.rollback()
            return False
    
    def get_user_preference(self, user_hash: str, item: str) -> Optional[Dict[str, Any]]:
        """
        Get user's preference for a specific item
        
        Args:
            user_hash: User's PSID hash
            item: The expense item to look up
            
        Returns:
            User's preference dict or None if not found
        """
        try:
            user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
            
            if not user or not user.preferences:
                return None
            
            preferences = user.preferences
            category_mappings = preferences.get('category_mappings', {})
            
            item_key = item.lower().strip()
            return category_mappings.get(item_key)
            
        except Exception as e:
            self.logger.error(f"Failed to get user preference: {e}")
            return None
    
    def get_user_patterns(self, user_hash: str) -> Dict[str, Any]:
        """
        Get user's spending patterns to help with categorization
        
        Args:
            user_hash: User's PSID hash
            
        Returns:
            Dict with user patterns and preferences
        """
        try:
            user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
            
            if not user:
                return {'is_new_user': True, 'patterns': {}}
            
            # Get recent expense patterns
            from models import Expense
            recent_expenses = db.session.query(Expense).filter(
                Expense.user_id == user_hash
            ).order_by(Expense.created_at.desc()).limit(50).all()
            
            # Analyze patterns
            category_frequency = {}
            avg_amounts_by_category = {}
            
            for expense in recent_expenses:
                cat = expense.category.lower()
                amount = float(expense.amount)
                
                category_frequency[cat] = category_frequency.get(cat, 0) + 1
                
                if cat not in avg_amounts_by_category:
                    avg_amounts_by_category[cat] = []
                avg_amounts_by_category[cat].append(amount)
            
            # Calculate averages
            for cat in avg_amounts_by_category:
                avg_amounts_by_category[cat] = sum(avg_amounts_by_category[cat]) / len(avg_amounts_by_category[cat])
            
            return {
                'is_new_user': len(recent_expenses) < 5,
                'patterns': {
                    'category_frequency': category_frequency,
                    'avg_amounts_by_category': avg_amounts_by_category,
                    'total_expenses': len(recent_expenses),
                    'most_common_category': max(category_frequency.items(), key=lambda x: x[1])[0] if category_frequency else None
                },
                'preferences': user.preferences or {}
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get user patterns: {e}")
            return {'is_new_user': True, 'patterns': {}}
    
    def suggest_category_based_on_history(self, user_hash: str, item: str, amount: float) -> Optional[str]:
        """
        Suggest a category based on user's historical patterns
        
        Args:
            user_hash: User's PSID hash
            item: The expense item
            amount: The expense amount
            
        Returns:
            Suggested category or None
        """
        # First check for explicit user preference
        preference = self.get_user_preference(user_hash, item)
        if preference:
            return preference['category']
        
        # Get user patterns
        patterns = self.get_user_patterns(user_hash)
        
        if patterns['is_new_user']:
            return None  # No history to base suggestions on
        
        # Look for similar amounts in user's history
        avg_amounts = patterns['patterns'].get('avg_amounts_by_category', {})
        
        best_match = None
        smallest_diff = float('inf')
        
        for category, avg_amount in avg_amounts.items():
            diff = abs(amount - avg_amount) / avg_amount
            if diff < smallest_diff and diff < 0.5:  # Within 50% of typical amount
                smallest_diff = diff
                best_match = category
        
        return best_match
    
    def record_clarification_interaction(self, user_hash: str, item: str, 
                                       options_shown: List[str], choice_made: str) -> None:
        """
        Record a clarification interaction for analytics and improvement
        
        Args:
            user_hash: User's PSID hash
            item: The ambiguous item
            options_shown: List of options presented to user
            choice_made: The option the user selected
        """
        try:
            user = self._get_or_create_user(user_hash)
            
            # Get existing interaction history
            preferences = user.preferences or {}
            
            if 'clarification_history' not in preferences:
                preferences['clarification_history'] = []
            
            # Add this interaction
            interaction = {
                'item': item,
                'options_shown': options_shown,
                'choice_made': choice_made,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            preferences['clarification_history'].append(interaction)
            
            # Keep only last 50 interactions
            preferences['clarification_history'] = preferences['clarification_history'][-50:]
            
            # Update interaction stats
            if 'interaction_stats' not in preferences:
                preferences['interaction_stats'] = {}
            
            preferences['interaction_stats']['total_clarifications'] = \
                preferences['interaction_stats'].get('total_clarifications', 0) + 1
            
            user.preferences = preferences
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"Failed to record clarification interaction: {e}")
            db.session.rollback()
    
    def _get_or_create_user(self, user_hash: str) -> User:
        """Get existing user or create new one"""
        user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
        
        if not user:
            user = User()
            user.user_id_hash = user_hash
            user.platform = 'messenger'
            user.preferences = {}
            user.created_at = datetime.utcnow()
            user.last_interaction = datetime.utcnow()
            db.session.add(user)
            db.session.flush()
        
        return user


# Initialize the global learning system
user_learning_system = UserLearningSystem()