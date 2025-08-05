"""Facebook Messenger message handling via Graph API"""
import os
import logging
import requests
import json
from utils.expense import process_expense_message

logger = logging.getLogger(__name__)

# Facebook configuration
FACEBOOK_PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "default_token")
FACEBOOK_API_VERSION = "v17.0"

def handle_facebook_message(sender_id, message_text):
    """Process Facebook Messenger message and send response"""
    try:
        logger.info(f"Processing Facebook message from {sender_id}: {message_text}")
        
        # Generate unique message ID
        unique_id = f"fb_{sender_id}_{int(datetime.now().timestamp())}"
        
        # Process the expense
        result = process_expense_message(
            user_identifier=sender_id,
            message=message_text,
            platform='facebook',
            unique_id=unique_id
        )
        
        # Send response back to user
        response_sent = send_facebook_message(sender_id, result['message'])
        
        if response_sent:
            logger.info(f"Facebook response sent successfully to {sender_id}")
        else:
            logger.error(f"Failed to send Facebook response to {sender_id}")
        
        return result['message']
        
    except Exception as e:
        logger.error(f"Error handling Facebook message: {str(e)}")
        # Send error message to user
        error_message = "Sorry, there was an error processing your expense. Please try again."
        send_facebook_message(sender_id, error_message)
        return error_message

def send_facebook_message(recipient_id, message_text):
    """Send Facebook Messenger message via Graph API"""
    try:
        url = f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/me/messages"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            'recipient': {'id': recipient_id},
            'message': {'text': message_text},
            'access_token': FACEBOOK_PAGE_ACCESS_TOKEN
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(data))
        
        if response.status_code == 200:
            logger.info(f"Facebook message sent successfully: {response.json().get('message_id')}")
            return True
        else:
            logger.error(f"Failed to send Facebook message: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
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
