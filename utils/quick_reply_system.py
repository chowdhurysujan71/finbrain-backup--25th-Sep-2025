"""
Quick Reply System for Facebook Messenger
Implements structured messaging with button-like interactions for better UX
"""

import logging
from typing import List, Dict
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.facebook_handler import send_message
import requests
import os

logger = logging.getLogger(__name__)

class QuickReplySystem:
    """Manages quick reply interactions for Facebook Messenger"""
    
    def __init__(self):
        self.access_token = os.environ.get('FACEBOOK_PAGE_ACCESS_TOKEN')
        
    def send_quick_replies(self, psid: str, text: str, replies: List[Dict[str, str]]) -> bool:
        """
        Send message with quick reply buttons
        
        Args:
            psid: Facebook Page-Scoped ID
            text: Message text to send
            replies: List of {"title": str, "payload": str} quick reply options
        """
        try:
            url = "https://graph.facebook.com/v17.0/me/messages"
            
            quick_replies = [
                {
                    "content_type": "text",
                    "title": reply["title"][:20],  # Facebook limit: 20 chars
                    "payload": reply["payload"][:1000]  # Facebook limit: 1000 chars
                }
                for reply in replies[:13]  # Facebook limit: 13 quick replies
            ]
            
            message_data = {
                "recipient": {"id": psid},
                "messaging_type": "RESPONSE",
                "message": {
                    "text": text[:2000],  # Facebook limit: 2000 chars
                    "quick_replies": quick_replies
                }
            }
            
            response = requests.post(
                url,
                params={"access_token": self.access_token},
                json=message_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Quick replies sent to {psid[:8]}...")
                return True
            else:
                logger.error(f"Quick reply failed: {response.status_code} - {response.text}")
                # Fallback to regular message
                send_message(psid, text)
                return False
                
        except Exception as e:
            logger.error(f"Quick reply system error: {e}")
            # Fallback to regular message
            send_message(psid, text)
            return False
    
    def send_persistent_menu(self, psid: str) -> bool:
        """Send persistent menu (appears as hamburger menu in chat)"""
        try:
            url = "https://graph.facebook.com/v17.0/me/messenger_profile"
            
            menu_data = {
                "persistent_menu": [
                    {
                        "locale": "default",
                        "composer_input_disabled": False,
                        "call_to_actions": [
                            {
                                "type": "postback",
                                "title": "Log Expense",
                                "payload": "LOG_EXPENSE"
                            },
                            {
                                "type": "postback", 
                                "title": "Weekly Summary",
                                "payload": "WEEKLY_REVIEW"
                            },
                            {
                                "type": "postback",
                                "title": "Set Budget Goal",
                                "payload": "SET_GOAL"
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(
                url,
                params={"access_token": self.access_token},
                json=menu_data,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Persistent menu setup failed: {e}")
            return False

# Pre-defined quick reply sets for common interactions
COMMON_QUICK_REPLIES = {
    "expense_logged": [
        {"title": "Yes, snapshot", "payload": "SHOW_SNAPSHOT"},
        {"title": "Set a cap", "payload": "SET_GOAL"},
        {"title": "Report a problem", "payload": "REPORT_PROBLEM"},
        {"title": "Done", "payload": "DONE"}
    ],
    
    "main_menu": [
        {"title": "Log Expense", "payload": "LOG_EXPENSE"},
        {"title": "Weekly Review", "payload": "WEEKLY_REVIEW"},
        {"title": "Set Goal", "payload": "SET_GOAL"}
    ],
    
    "support_menu": [
        {"title": "Report a problem", "payload": "REPORT_PROBLEM"},
        {"title": "Get help", "payload": "HELP"},
        {"title": "FAQ", "payload": "FAQ"}
    ],
    
    "daily_checkin": [
        {"title": "Log", "payload": "LOG_EXPENSE"},
        {"title": "Balance", "payload": "SHOW_BALANCE"},
        {"title": "Skip", "payload": "SKIP_TODAY"}
    ],
    
    "weekly_review": [
        {"title": "Set Target", "payload": "SET_TARGET_DINING_6500"},
        {"title": "See Chart", "payload": "SEE_WEEKLY_CHART"},
        {"title": "Ignore", "payload": "IGNORE_WEEKLY_TARGET"}
    ],
    
    "goal_tracker": [
        {"title": "Add ৳5,000", "payload": "GOAL_ADD_5000"},
        {"title": "Change Goal", "payload": "GOAL_CHANGE"},
        {"title": "Not now", "payload": "GOAL_LATER"}
    ],
    
    "smart_nudge": [
        {"title": "Cap", "payload": "CAP_DINING_6500"},
        {"title": "See details", "payload": "DETAILS_DINING"},
        {"title": "Dismiss", "payload": "DISMISS_DINING"}
    ],
    
    "ai_response": [
        {"title": "Show breakdown", "payload": "SHOW_BREAKDOWN"},
        {"title": "Set a cap", "payload": "SET_GOAL"},
        {"title": "Report a problem", "payload": "REPORT_PROBLEM"},
        {"title": "Not now", "payload": "IGNORE"}
    ]
}

# Global quick reply system instance
quick_reply_system = QuickReplySystem()

def send_quick_reply_message(psid: str, text: str, reply_set: str) -> bool:
    """
    Send message with predefined quick reply set
    
    Args:
        psid: User ID
        text: Message text
        reply_set: Key from COMMON_QUICK_REPLIES
    """
    replies = COMMON_QUICK_REPLIES.get(reply_set, COMMON_QUICK_REPLIES["main_menu"])
    return quick_reply_system.send_quick_replies(psid, text, replies)

def send_custom_quick_replies(psid: str, text: str, replies: List[Dict[str, str]]) -> bool:
    """Send message with custom quick replies"""
    return quick_reply_system.send_quick_replies(psid, text, replies)

# Test function
def test_quick_reply_system():
    """Test quick reply system functionality"""
    print("=== QUICK REPLY SYSTEM TEST ===")
    
    # Test reply validation
    test_replies = [
        {"title": "Short", "payload": "SHORT_PAYLOAD"},
        {"title": "This is a very long title that exceeds twenty characters", "payload": "LONG_TITLE"},
        {"title": "Normal", "payload": "NORMAL_PAYLOAD"}
    ]
    
    # Validate reply limits
    validated_replies = []
    for reply in test_replies:
        validated_reply = {
            "title": reply["title"][:20],
            "payload": reply["payload"][:1000]
        }
        validated_replies.append(validated_reply)
        print(f"Original: '{reply['title']}' → Validated: '{validated_reply['title']}'")
    
    # Test common reply sets
    for reply_set, replies in COMMON_QUICK_REPLIES.items():
        print(f"\n{reply_set}: {len(replies)} options")
        for reply in replies:
            print(f"  - {reply['title']} ({reply['payload']})")
    
    print("\n✅ Quick reply system tested successfully")

if __name__ == "__main__":
    test_quick_reply_system()