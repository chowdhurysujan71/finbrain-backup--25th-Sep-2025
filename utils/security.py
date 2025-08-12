"""Security functions for user data protection"""
import hashlib
import logging

logger = logging.getLogger(__name__)

def hash_user_id(user_identifier):
    """Hash user identifier with SHA-256 for privacy protection"""
    try:
        if not user_identifier:
            raise ValueError("User identifier cannot be empty")
        
        # Ensure consistent string format
        user_str = str(user_identifier).strip()
        
        # Create SHA-256 hash
        hash_object = hashlib.sha256(user_str.encode('utf-8'))
        hashed_id = hash_object.hexdigest()
        
        logger.debug(f"User ID hashed successfully")
        return hashed_id
        
    except Exception as e:
        logger.error(f"Error hashing user ID: {str(e)}")
        raise

def hash_psid(psid):
    """Create a secure hash of PSID for logging (alias for hash_user_id)"""
    return hash_user_id(psid)



def validate_facebook_psid(psid):
    """Validate Facebook Page-Scoped User ID"""
    try:
        if not psid:
            return False
        
        # PSID should be a numeric string
        if psid.isdigit() and len(psid) > 5:
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error validating Facebook PSID: {str(e)}")
        return False

def sanitize_input(text):
    """Sanitize user input to prevent injection attacks"""
    try:
        if not text:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = str(text).strip()
        
        # Remove SQL injection attempts
        dangerous_chars = [';', '--', '/*', '*/', 'xp_', 'sp_']
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized[:500]  # Limit length
        
    except Exception as e:
        logger.error(f"Error sanitizing input: {str(e)}")
        return ""
