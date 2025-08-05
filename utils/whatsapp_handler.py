"""WhatsApp message handling via Twilio"""
import os
import logging
import requests
from utils.expense import process_expense_message
from utils.security import hash_user_id

logger = logging.getLogger(__name__)

# Twilio configuration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "default_sid")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "default_token")
TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

def handle_whatsapp_message(from_number, message_body, message_sid):
    """Process WhatsApp message and send response"""
    try:
        logger.info(f"Processing WhatsApp message from {from_number}: {message_body}")
        
        # Process the expense
        result = process_expense_message(
            user_identifier=from_number,
            message=message_body,
            platform='whatsapp',
            unique_id=message_sid
        )
        
        # Send response back to user
        response_sent = send_whatsapp_message(from_number, result['message'])
        
        if response_sent:
            logger.info(f"WhatsApp response sent successfully to {from_number}")
        else:
            logger.error(f"Failed to send WhatsApp response to {from_number}")
        
        return result['message']
        
    except Exception as e:
        logger.error(f"Error handling WhatsApp message: {str(e)}")
        # Send error message to user
        error_message = "Sorry, there was an error processing your expense. Please try again."
        send_whatsapp_message(from_number, error_message)
        return error_message

def send_whatsapp_message(to_number, message):
    """Send WhatsApp message via Twilio API"""
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        
        data = {
            'From': TWILIO_WHATSAPP_NUMBER,
            'To': to_number,
            'Body': message
        }
        
        response = requests.post(
            url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data=data
        )
        
        if response.status_code == 201:
            logger.info(f"WhatsApp message sent successfully: {response.json().get('sid')}")
            return True
        else:
            logger.error(f"Failed to send WhatsApp message: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return False

def send_whatsapp_report(user_phone, report_message):
    """Send automated report via WhatsApp"""
    try:
        logger.info(f"Sending WhatsApp report to {user_phone}")
        return send_whatsapp_message(user_phone, report_message)
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp report: {str(e)}")
        return False
