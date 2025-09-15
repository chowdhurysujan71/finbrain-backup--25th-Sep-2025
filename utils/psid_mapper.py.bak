"""
PSID Mapper: Reverse lookup from user_id_hash to original Facebook PSID
Fixes the critical Messenger delivery issue by mapping hashes back to valid PSIDs
"""

import logging
from typing import Optional
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

def get_original_psid(user_id_hash: str) -> Optional[str]:
    """
    Get the original Facebook PSID from user_id_hash using expenses table lookup
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        
    Returns:
        Original Facebook PSID (numeric string) or None if not found
    """
    try:
        # Look up original PSID from expenses table (legacy user_id field)
        result = db.session.execute(text(
            "SELECT DISTINCT user_id FROM expenses WHERE user_id_hash = :hash AND user_id ~ '^[0-9]+$' LIMIT 1"
        ), {"hash": user_id_hash}).fetchone()
        
        if result and result[0]:
            original_psid = result[0]
            
            # Validate it's a proper Facebook PSID (numeric, 10+ digits)
            if original_psid.isdigit() and len(original_psid) >= 10:
                logger.debug(f"Mapped hash {user_id_hash[:16]}... -> PSID {original_psid}")
                return original_psid
            else:
                logger.warning(f"Invalid PSID format found: {original_psid}")
                return None
        else:
            logger.warning(f"No original PSID found for hash {user_id_hash[:16]}...")
            return None
            
    except Exception as e:
        logger.error(f"PSID lookup failed for hash {user_id_hash[:16]}...: {e}")
        return None

def send_message_with_hash(user_id_hash: str, message_text: str) -> bool:
    """
    Send Facebook message using user_id_hash by reverse-looking up original PSID
    
    Args:
        user_id_hash: SHA-256 hashed user identifier
        message_text: Message to send
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        # Get original PSID
        original_psid = get_original_psid(user_id_hash)
        
        if not original_psid:
            logger.error(f"Cannot send message: no PSID mapping for hash {user_id_hash[:16]}...")
            return False
        
        # Send message using original PSID
        from utils.facebook_handler import send_facebook_message
        return send_facebook_message(original_psid, message_text)
        
    except Exception as e:
        logger.error(f"Message sending failed for hash {user_id_hash[:16]}...: {e}")
        return False