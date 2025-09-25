"""
User ID Normalizer - Ensures consistent user_id_hash usage across the platform
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class UserIdNormalizer:
    """Handles user ID normalization and prevents schema drift"""
    
    def __init__(self):
        self.normalization_warnings = []
    
    def normalize_expense_record(self, expense_data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize expense record to ensure user_id_hash is always present
        
        Args:
            expense_data: Dictionary containing expense data
            
        Returns:
            Normalized expense data with guaranteed user_id_hash
        """
        normalized = expense_data.copy()
        
        # Ensure user_id_hash is present
        if 'user_id_hash' not in normalized and 'user_id' in normalized:
            normalized['user_id_hash'] = normalized['user_id']
            logger.debug("Normalized user_id to user_id_hash for expense")
        
        # Ensure both fields are consistent (backwards compatibility)
        if 'user_id_hash' in normalized and 'user_id' not in normalized:
            normalized['user_id'] = normalized['user_id_hash']
        
        return normalized
    
    def get_user_identifier(self, user_data: dict[str, Any]) -> str:
        """
        Get the canonical user identifier, preferring user_id_hash
        
        Args:
            user_data: Dictionary containing user data
            
        Returns:
            The canonical user identifier
        """
        # Prefer user_id_hash as it's the current standard
        if 'user_id_hash' in user_data and user_data['user_id_hash']:
            return user_data['user_id_hash']
        
        # Fall back to user_id for backwards compatibility
        if 'user_id' in user_data and user_data['user_id']:
            warning = "Using legacy user_id field - should migrate to user_id_hash"
            if warning not in self.normalization_warnings:
                self.normalization_warnings.append(warning)
                logger.warning(warning)
            return user_data['user_id']
        
        raise ValueError("No valid user identifier found in user data")
    
    def validate_user_identifier(self, user_id: str) -> bool:
        """
        Validate that user identifier follows expected format
        
        Args:
            user_id: User identifier to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not user_id or not isinstance(user_id, str):
            return False
        
        # Should be a SHA-256 hash (64 hex characters)
        if len(user_id) == 64 and all(c in '0123456789abcdef' for c in user_id.lower()):
            return True
        
        # Legacy format validation (may be different)
        if len(user_id) > 10:  # Reasonable minimum length
            return True
        
        return False

# Global normalizer instance
user_id_normalizer = UserIdNormalizer()

def ensure_user_id_hash(data: dict[str, Any]) -> dict[str, Any]:
    """
    Convenience function to ensure user_id_hash is present in data
    
    Args:
        data: Dictionary that should contain user identification
        
    Returns:
        Data with normalized user identification
    """
    return user_id_normalizer.normalize_expense_record(data)