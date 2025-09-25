"""24-hour policy compliance for Facebook Messenger"""
import logging
from datetime import datetime, timedelta

from utils.user_manager import resolve_user_id

logger = logging.getLogger(__name__)

def is_within_24_hour_window(psid: str) -> bool:
    """Check if user's last message was within 24 hours (policy-safe to respond)"""
    try:
        from models import User
        
        user_hash = resolve_user_id(psid=psid)
        user = User.query.filter_by(user_id_hash=user_hash).first()
        
        if not user or not user.last_user_message_at:
            # First interaction - always allowed
            return True
            
        # Check if within 24-hour window
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        is_within_window = user.last_user_message_at > cutoff_time
        
        if not is_within_window:
            logger.info(f"Message outside 24h window for PSID {psid[:8]}*** - blocking outbound")
        
        return is_within_window
        
    except Exception as e:
        logger.error(f"Error checking 24h window: {str(e)}")
        # Fail-safe: allow response if we can't check
        return True

def update_user_message_timestamp(psid: str):
    """Update last_user_message_at timestamp for 24-hour policy tracking"""
    try:
        from models import User, db
        
        user_hash = resolve_user_id(psid=psid)
        user = User.query.filter_by(user_id_hash=user_hash).first()
        
        if not user:
            user = User(
                user_id_hash=user_hash,
                platform='messenger',
                last_user_message_at=datetime.utcnow()
            )
            db.session.add(user)
        else:
            user.last_user_message_at = datetime.utcnow()
            user.last_interaction = datetime.utcnow()
        
        db.session.commit()
        logger.debug(f"Updated 24h timestamp for PSID {psid[:8]}***")
        
    except Exception as e:
        logger.error(f"Error updating user timestamp: {str(e)}")

def hash_psid(psid: str) -> str:
    """Generate SHA-256 hash of PSID"""
    import hashlib
    return hashlib.sha256(psid.encode()).hexdigest()

def can_send_proactive_message(psid: str) -> bool:
    """Check if we can send proactive messages (scheduled reports, etc.)
    
    For MVP: Returns False - no scheduled outbound messages allowed
    """
    logger.info(f"Proactive message blocked for PSID {psid[:8]}*** - MVP policy")
    return False