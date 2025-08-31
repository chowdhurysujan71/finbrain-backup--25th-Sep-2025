"""
Report Feedback Context Management
Handles temporary context tracking for report feedback collection
"""

import time
import logging
import secrets
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# CRITICAL FIX: Global context storage to persist across router instances
# In production, this should be Redis-backed for scalability
_GLOBAL_FEEDBACK_CONTEXTS: Dict[str, Dict] = {}

class FeedbackContextManager:
    """Manages temporary feedback contexts for report responses"""
    
    def __init__(self, context_timeout_hours: int = 24):
        """Initialize context manager with configurable timeout"""
        self.timeout_hours = context_timeout_hours
        logger.info(f"Feedback context manager initialized: timeout={context_timeout_hours}h")
    
    def generate_context_id(self, user_id_hash: str) -> str:
        """
        Generate unique context ID for a report
        Format: timestamp_random_user_suffix
        """
        try:
            timestamp = int(time.time())
            random_suffix = secrets.token_hex(3)  # 6 characters
            user_suffix = user_id_hash[-4:] if len(user_id_hash) >= 4 else user_id_hash
            
            context_id = f"{timestamp}_{random_suffix}_{user_suffix}"
            logger.debug(f"Generated context ID: {context_id}")
            return context_id
            
        except Exception as e:
            logger.error(f"Failed to generate context ID: {e}")
            # Fallback to simpler format
            return f"{int(time.time())}_{secrets.token_hex(4)}"
    
    def set_context(self, user_id_hash: str, report_context_id: str) -> bool:
        """
        Set feedback context for user (optimized)
        Returns True if successful, False otherwise
        """
        try:
            # Skip cleanup for performance - cleanup only when needed
            expires_at = datetime.utcnow() + timedelta(hours=self.timeout_hours)
            
            # Store context in global storage (single operation)
            _GLOBAL_FEEDBACK_CONTEXTS[user_id_hash] = {
                'report_context_id': report_context_id,
                'created_at': datetime.utcnow(),
                'expires_at': expires_at
            }
            
            logger.debug(f"Set feedback context for user {user_id_hash[:8]}...: {report_context_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set feedback context: {e}")
            return False
    
    def get_context(self, user_id_hash: str) -> Optional[str]:
        """
        Get active feedback context for user
        Returns context_id if active, None if expired or not found
        """
        try:
            context = _GLOBAL_FEEDBACK_CONTEXTS.get(user_id_hash)
            
            if not context:
                logger.debug(f"No feedback context found for user {user_id_hash[:8]}...")
                return None
            
            # Check if expired
            if datetime.utcnow() > context['expires_at']:
                logger.debug(f"Feedback context expired for user {user_id_hash[:8]}...")
                self._remove_context(user_id_hash)
                return None
            
            report_context_id = context['report_context_id']
            logger.debug(f"Retrieved active context for user {user_id_hash[:8]}...: {report_context_id}")
            return report_context_id
            
        except Exception as e:
            logger.error(f"Failed to get feedback context: {e}")
            return None
    
    def clear_context(self, user_id_hash: str) -> bool:
        """
        Clear feedback context for user (after feedback recorded)
        Returns True if context was cleared, False if not found
        """
        try:
            if user_id_hash in _GLOBAL_FEEDBACK_CONTEXTS:
                context_id = _GLOBAL_FEEDBACK_CONTEXTS[user_id_hash].get('report_context_id', 'unknown')
                self._remove_context(user_id_hash)
                logger.debug(f"Cleared feedback context for user {user_id_hash[:8]}...: {context_id}")
                return True
            else:
                logger.debug(f"No context to clear for user {user_id_hash[:8]}...")
                return False
                
        except Exception as e:
            logger.error(f"Failed to clear feedback context: {e}")
            return False
    
    def has_active_context(self, user_id_hash: str) -> bool:
        """
        Check if user has active feedback context
        """
        return self.get_context(user_id_hash) is not None
    
    def _remove_context(self, user_id_hash: str):
        """Internal method to remove context"""
        _GLOBAL_FEEDBACK_CONTEXTS.pop(user_id_hash, None)
    
    def _cleanup_expired_contexts(self):
        """Clean up expired contexts to prevent memory growth"""
        try:
            current_time = datetime.utcnow()
            expired_users = []
            
            for user_id_hash, context in _GLOBAL_FEEDBACK_CONTEXTS.items():
                if current_time > context['expires_at']:
                    expired_users.append(user_id_hash)
            
            for user_id_hash in expired_users:
                self._remove_context(user_id_hash)
            
            if expired_users:
                logger.debug(f"Cleaned up {len(expired_users)} expired feedback contexts")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired contexts: {e}")
    
    def get_stats(self) -> Dict:
        """Get context manager statistics"""
        try:
            self._cleanup_expired_contexts()
            return {
                'active_contexts': len(_GLOBAL_FEEDBACK_CONTEXTS),
                'timeout_hours': self.timeout_hours,
                'oldest_context': min(
                    (ctx['created_at'] for ctx in _GLOBAL_FEEDBACK_CONTEXTS.values()),
                    default=None
                )
            }
        except Exception as e:
            logger.error(f"Failed to get context stats: {e}")
            return {'error': str(e)}

# Global instance - initialized once per application
feedback_context_manager = FeedbackContextManager()

def generate_report_context_id(user_id_hash: str) -> str:
    """Generate new report context ID"""
    return feedback_context_manager.generate_context_id(user_id_hash)

def set_feedback_context(user_id_hash: str, report_context_id: str) -> bool:
    """Set feedback context for user after sending report"""
    return feedback_context_manager.set_context(user_id_hash, report_context_id)

def get_feedback_context(user_id_hash: str) -> Optional[str]:
    """Get active feedback context for user (if expecting feedback)"""
    return feedback_context_manager.get_context(user_id_hash)

def clear_feedback_context(user_id_hash: str) -> bool:
    """Clear feedback context after feedback recorded"""
    return feedback_context_manager.clear_context(user_id_hash)

def has_pending_feedback(user_id_hash: str) -> bool:
    """Check if user has pending feedback context"""
    return feedback_context_manager.has_active_context(user_id_hash)