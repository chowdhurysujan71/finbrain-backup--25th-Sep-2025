"""Facebook Messenger message handling via Graph API"""
import os
import logging
import json
import time
from datetime import datetime
from utils.expense import process_expense_message
from .logger import log_graph_call

# Lazy import for production safety - this function is defined below

logger = logging.getLogger(__name__)

# Facebook configuration
FACEBOOK_PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "default_token")
FACEBOOK_API_VERSION = "v17.0"

# Legacy handler - now replaced by MVP router
# Message processing is now handled in utils/mvp_router.py

def send_facebook_message(recipient_id, message_text):
    """Send Facebook Messenger message via Graph API with structured logging"""
    endpoint = f"/{FACEBOOK_API_VERSION}/me/messages"
    start_time = time.time()
    
    try:
        # Lazy import for production safety
        import requests
        
        url = f"https://graph.facebook.com{endpoint}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            'recipient': {'id': recipient_id},
            'message': {'text': message_text},
            'access_token': FACEBOOK_PAGE_ACCESS_TOKEN
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(data))
        duration_ms = (time.time() - start_time) * 1000
        
        # Log Graph API call with structured logging
        log_graph_call(endpoint, "POST", response.status_code, duration_ms)
        
        if response.status_code == 200:
            response_data = response.json()
            message_id = response_data.get('message_id', 'unknown')
            logger.info(f"Facebook message sent successfully: {message_id}")
            return True
        else:
            logger.error(f"Failed to send Facebook message: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_graph_call(endpoint, "POST", None, duration_ms, str(e))
        logger.error(f"Error sending Facebook message: {str(e)}")
        return False

def send_facebook_report(user_psid, report_message):
    """Send automated report via Facebook Messenger"""
    try:
        logger.info(f"Sending Facebook report to {user_psid}")
        return send_facebook_message(user_psid, report_message)
        
    except Exception as e:
        logger.error(f"Error sending Facebook report: {str(e)}")
        return False
