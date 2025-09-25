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
        
        logger.debug("User ID hashed successfully")
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
    """Enhanced sanitize user input to prevent injection attacks and XSS"""
    try:
        if not text:
            return ""
        
        # Convert to string and strip
        sanitized = str(text).strip()
        
        # Remove control characters (except newline, carriage return, tab)
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in ['\n', '\r', '\t'])
        
        # Remove/escape potentially dangerous characters for XSS
        xss_patterns = [
            '<script', '</script>', '<iframe', '</iframe>', '<object', '</object>',
            'javascript:', 'vbscript:', 'onload=', 'onerror=', 'onclick=', 'onmouseover='
        ]
        for pattern in xss_patterns:
            sanitized = sanitized.replace(pattern, '')
            sanitized = sanitized.replace(pattern.upper(), '')
        
        # Remove SQL injection attempts
        sql_patterns = [';', '--', '/*', '*/', 'xp_', 'sp_', 'DROP TABLE', 'DELETE FROM', 
                       'INSERT INTO', 'UPDATE SET', 'UNION SELECT', 'SELECT * FROM']
        for pattern in sql_patterns:
            sanitized = sanitized.replace(pattern, '')
            sanitized = sanitized.replace(pattern.upper(), '')
        
        # Limit length to prevent DoS
        if len(sanitized) > 2000:
            sanitized = sanitized[:2000]
        
        # Preserve Bengali/unicode characters but remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        return sanitized
        
    except Exception as e:
        logger.error(f"Error sanitizing input: {str(e)}")
        return ""
