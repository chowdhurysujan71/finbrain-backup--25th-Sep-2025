"""Facebook Messenger message handling via Graph API"""
import logging
import os
import time

from .logger import log_graph_call

# Lazy import for production safety - this function is defined below

logger = logging.getLogger(__name__)

# Facebook configuration
FACEBOOK_PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "default_token")
FACEBOOK_API_VERSION = "v17.0"

# Legacy handler - now replaced by MVP router
# Message processing is now handled in utils/mvp_router.py

def send_facebook_message(recipient_id, message_text):
    """Send Facebook Messenger message via Graph API with structured logging and PSID validation"""
    endpoint = f"/{FACEBOOK_API_VERSION}/me/messages"
    start_time = time.time()
    
    try:
        # Use the new validated Facebook client
        from fb_client import is_valid_psid, send_text
        
        # Clear PSID validation with detailed error logging
        if not is_valid_psid(recipient_id):
            # In non-production, check dev allowlist before failing
            if os.getenv("ENV") != "production":
                from utils.allowlist import is_dev_psid
                if is_dev_psid(recipient_id):
                    logger.info(f"Dev PSID allowed: {recipient_id} (non-production)")
                else:
                    duration_ms = (time.time() - start_time) * 1000
                    log_graph_call(endpoint, "POST", None, duration_ms, f"Invalid PSID: {recipient_id}")
                    logger.error(f"PSID validation failed: '{recipient_id}' is not a valid Facebook page-scoped ID. Must be 10+ digit numeric string from real chat.")
                    raise ValueError(f"Invalid PSID '{recipient_id}'. Must be a numeric page-scoped ID from a real chat.")
            else:
                duration_ms = (time.time() - start_time) * 1000
                log_graph_call(endpoint, "POST", None, duration_ms, f"Invalid PSID: {recipient_id}")
                logger.error(f"PSID validation failed: '{recipient_id}' is not a valid Facebook page-scoped ID. Must be 10+ digit numeric string from real chat.")
                raise ValueError(f"Invalid PSID '{recipient_id}'. Must be a numeric page-scoped ID from a real chat.")
        
        # Send via validated client
        response_data = send_text(recipient_id, message_text)
        duration_ms = (time.time() - start_time) * 1000
        
        # Log successful Graph API call
        log_graph_call(endpoint, "POST", 200, duration_ms)
        
        message_id = response_data.get('message_id', 'unknown')
        logger.info(f"Facebook message sent successfully: {message_id}")
        return True
        
    except ValueError as ve:
        # PSID validation error - already logged above
        duration_ms = (time.time() - start_time) * 1000
        log_graph_call(endpoint, "POST", None, duration_ms, str(ve))
        raise ve  # Re-raise for proper error handling upstream
        
    except RuntimeError as re:
        # Facebook API error from fb_client
        duration_ms = (time.time() - start_time) * 1000
        log_graph_call(endpoint, "POST", None, duration_ms, str(re))
        logger.error(f"Facebook API error: {str(re)}")
        raise re  # Re-raise for proper error handling upstream
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_graph_call(endpoint, "POST", None, duration_ms, str(e))
        logger.error(f"Unexpected error sending Facebook message: {str(e)}")
        raise e  # Re-raise for proper error handling upstream

def send_facebook_report(user_psid, report_message):
    """Send automated report via Facebook Messenger"""
    try:
        logger.info(f"Sending Facebook report to {user_psid}")
        return send_facebook_message(user_psid, report_message)
        
    except Exception as e:
        logger.error(f"Error sending Facebook report: {str(e)}")
        return False
