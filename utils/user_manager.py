"""
User management and engagement tracking for FinBrain
Handles user creation, updates, and onboarding state management
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, date
from app import db
from models import User
from utils.security import hash_psid

logger = logging.getLogger(__name__)

class UserManager:
    """Manages user lifecycle, onboarding, and engagement tracking"""
    
    def get_or_create_user(self, psid: str) -> Dict[str, Any]:
        """Get existing user or create new one with engagement tracking"""
        # Check if we already have a hash (64 chars) or need to hash a PSID
        if len(psid) == 64:  # Already hashed
            psid_hash = psid
        else:
            psid_hash = hash_psid(psid)
        
        try:
            user = User.query.filter_by(user_id_hash=psid_hash).first()
            
            if not user:
                # Create new user with engagement defaults
                user = User(
                    user_id_hash=psid_hash,
                    platform='messenger',
                    is_new=True,
                    has_completed_onboarding=False,
                    onboarding_step=0,
                    interaction_count=0,
                    first_name='',
                    income_range='',
                    primary_category='',
                    focus_area='',
                    preferences={}
                )
                db.session.add(user)
                db.session.commit()
                logger.info(f"Created new user: {psid_hash[:10]}...")
            
            # Update last interaction
            user.last_interaction = datetime.utcnow()
            user.interaction_count += 1
            db.session.commit()
            
            # Convert to dict for engagement engine
            return self._user_to_dict(user)
            
        except Exception as e:
            logger.error(f"Error managing user {psid_hash[:10]}...: {e}")
            db.session.rollback()
            # Return minimal user data for fallback
            return {
                'user_id_hash': psid_hash,
                'is_new': True,
                'has_completed_onboarding': False,
                'onboarding_step': 0,
                'interaction_count': 1,
                'first_name': '',
                'platform': 'messenger'
            }
    
    def update_user_onboarding(self, psid: str, updates: Dict[str, Any]) -> bool:
        """Update user onboarding data"""
        # Check if we already have a hash (64 chars) or need to hash a PSID
        if len(psid) == 64:  # Already hashed
            psid_hash = psid
        else:
            psid_hash = hash_psid(psid)
        
        try:
            user = User.query.filter_by(user_id_hash=psid_hash).first()
            if not user:
                logger.error(f"User not found for onboarding update: {psid_hash[:10]}...")
                return False
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)
                else:
                    logger.warning(f"Unknown user field: {key}")
            
            db.session.commit()
            logger.info(f"Updated user onboarding: {psid_hash[:10]}... step={user.onboarding_step}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user onboarding: {e}")
            db.session.rollback()
            return False
    
    def extract_first_name(self, message: str) -> str:
        """Extract first name from user message during onboarding"""
        # Simple name extraction - look for common patterns
        words = message.split()
        
        # Look for "I'm [name]" or "My name is [name]"
        for i, word in enumerate(words):
            if word.lower() in ['im', "i'm", 'name'] and i + 1 < len(words):
                next_word = words[i + 1]
                if next_word.lower() not in ['is', 'was', 'am']:
                    return next_word.capitalize()
            elif word.lower() == 'is' and i + 1 < len(words):
                return words[i + 1].capitalize()
        
        # If no clear pattern, return empty string
        return ''
    
    def _user_to_dict(self, user: User) -> Dict[str, Any]:
        """Convert User model to dict for engagement engine"""
        return {
            'user_id_hash': user.user_id_hash,
            'is_new': user.is_new,
            'has_completed_onboarding': user.has_completed_onboarding,
            'onboarding_step': user.onboarding_step,
            'interaction_count': user.interaction_count,
            'first_name': user.first_name or 'there',
            'income_range': user.income_range,
            'primary_category': user.primary_category,
            'focus_area': user.focus_area,
            'preferences': user.preferences or {},
            'platform': user.platform,
            'created_at': user.created_at,
            'last_interaction': user.last_interaction
        }
    
    def get_user_spending_summary(self, psid: str, days: int = 7) -> Dict[str, float]:
        """Get user's spending summary for engagement responses"""
        from models import Expense
        from datetime import timedelta
        
        # Check if we already have a hash (64 chars) or need to hash a PSID
        if len(psid) == 64:  # Already hashed
            psid_hash = psid
        else:
            psid_hash = hash_psid(psid)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        try:
            expenses = Expense.query.filter(
                Expense.user_id == psid_hash,
                Expense.created_at >= cutoff_date
            ).all()
            
            # Aggregate by category
            summary = {
                'food': 0.0,
                'shopping': 0.0,
                'bills': 0.0,
                'transport': 0.0,
                'other': 0.0
            }
            
            for expense in expenses:
                category = expense.category.lower()
                amount = float(expense.amount)
                
                if category in summary:
                    summary[category] += amount
                else:
                    summary['other'] += amount
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting spending summary: {e}")
            return {'food': 0.0, 'shopping': 0.0, 'bills': 0.0, 'transport': 0.0, 'other': 0.0}

# Global user manager instance
user_manager = UserManager()