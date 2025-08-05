"""Rate limiting functionality for message processing"""
import os
import logging
from datetime import datetime, date, timedelta
from utils.security import hash_user_id

logger = logging.getLogger(__name__)

# Rate limiting configuration
DAILY_MESSAGE_LIMIT = int(os.environ.get("DAILY_MESSAGE_LIMIT", "50"))
HOURLY_MESSAGE_LIMIT = int(os.environ.get("HOURLY_MESSAGE_LIMIT", "10"))

def check_rate_limit(user_identifier, platform):
    """Check if user has exceeded rate limits"""
    from models import RateLimit
    from app import db
    
    try:
        user_hash = hash_user_id(user_identifier)
        current_date = date.today()
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        # Get or create rate limit record
        rate_limit = RateLimit.query.filter_by(
            user_id_hash=user_hash,
            platform=platform
        ).first()
        
        if not rate_limit:
            rate_limit = RateLimit(
                user_id_hash=user_hash,
                platform=platform,
                daily_count=0,
                hourly_count=0,
                last_daily_reset=current_date,
                last_hourly_reset=current_hour
            )
            db.session.add(rate_limit)
        
        # Reset daily counter if needed
        if rate_limit.last_daily_reset < current_date:
            rate_limit.daily_count = 0
            rate_limit.last_daily_reset = current_date
        
        # Reset hourly counter if needed
        if rate_limit.last_hourly_reset < current_hour:
            rate_limit.hourly_count = 0
            rate_limit.last_hourly_reset = current_hour
        
        # Check limits
        if rate_limit.daily_count >= DAILY_MESSAGE_LIMIT:
            logger.warning(f"Daily rate limit exceeded for user {user_hash}")
            return False
        
        if rate_limit.hourly_count >= HOURLY_MESSAGE_LIMIT:
            logger.warning(f"Hourly rate limit exceeded for user {user_hash}")
            return False
        
        # Increment counters
        rate_limit.daily_count += 1
        rate_limit.hourly_count += 1
        rate_limit.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}")
        db.session.rollback()
        # Allow message in case of error
        return True

def get_rate_limit_status(user_identifier, platform):
    """Get current rate limit status for user"""
    try:
        user_hash = hash_user_id(user_identifier)
        
        rate_limit = RateLimit.query.filter_by(
            user_id_hash=user_hash,
            platform=platform
        ).first()
        
        if not rate_limit:
            return {
                'daily_remaining': DAILY_MESSAGE_LIMIT,
                'hourly_remaining': HOURLY_MESSAGE_LIMIT,
                'daily_limit': DAILY_MESSAGE_LIMIT,
                'hourly_limit': HOURLY_MESSAGE_LIMIT
            }
        
        return {
            'daily_remaining': max(0, DAILY_MESSAGE_LIMIT - rate_limit.daily_count),
            'hourly_remaining': max(0, HOURLY_MESSAGE_LIMIT - rate_limit.hourly_count),
            'daily_limit': DAILY_MESSAGE_LIMIT,
            'hourly_limit': HOURLY_MESSAGE_LIMIT,
            'daily_used': rate_limit.daily_count,
            'hourly_used': rate_limit.hourly_count
        }
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {str(e)}")
        return {
            'daily_remaining': DAILY_MESSAGE_LIMIT,
            'hourly_remaining': HOURLY_MESSAGE_LIMIT,
            'daily_limit': DAILY_MESSAGE_LIMIT,
            'hourly_limit': HOURLY_MESSAGE_LIMIT
        }
