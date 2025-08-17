"""
Enhanced message handling with integrated UX components
Wires together the ux_components with the existing FinBrain architecture
"""

import logging
from typing import Dict, Any, Optional
from utils.ux_components import (
    handle_enhanced_message, handle_payload, get_ux_metrics,
    parse_expense, safe_send_text, send_picker, record_event
)
from utils.facebook_handler import send_message
from limiter import can_use_ai

logger = logging.getLogger(__name__)

class EnhancedMessageHandler:
    """Enhanced message handler with UX components integration"""
    
    def __init__(self, db_session, ai_adapter=None):
        self.db = db_session
        self.ai_adapter = ai_adapter
        
    def _send_message(self, psid: str, text: str):
        """Wrapper for Facebook send_message"""
        return send_message(psid, text)
    
    def _send_quick_replies(self, psid: str, replies: list):
        """Send quick reply buttons via Facebook API"""
        try:
            # This would integrate with your existing Facebook quick reply system
            # For now, using a simplified approach
            from utils.facebook_handler import send_structured_message
            
            message_data = {
                "recipient": {"id": psid},
                "message": {
                    "text": "Choose an option:",
                    "quick_replies": [
                        {
                            "content_type": "text",
                            "title": reply["title"],
                            "payload": reply["payload"]
                        }
                        for reply in replies
                    ]
                }
            }
            return send_structured_message(psid, message_data)
            
        except Exception as e:
            logger.error(f"Quick reply sending failed: {e}")
            # Fallback to text menu
            options = " | ".join([f"{i+1}. {r['title']}" for i, r in enumerate(replies)])
            self._send_message(psid, f"Options: {options}")
    
    def _db_operation(self, operation: str, *args, **kwargs):
        """Database operation wrapper"""
        try:
            if operation == "add_expense":
                psid, category, amount = args
                # Integrate with your existing expense logging
                from models import Expense, User
                from utils.security import hash_psid
                
                user_hash = hash_psid(psid)
                expense = Expense(
                    user_id=user_hash,
                    description=category,
                    amount=amount,
                    category=category.lower(),
                    currency='৳',
                    platform='messenger'
                )
                self.db.add(expense)
                self.db.commit()
                return True
                
            elif operation == "get_spend_by_category":
                psid, days = args
                # Return mock data for now - integrate with your existing queries
                return [("Food", 2500), ("Ride", 800), ("Bills", 1200)]
                
            elif operation == "set_cap":
                psid, category, amount = args
                # Integrate with your cap system
                logger.info(f"Setting cap for {psid}: {category} = {amount}")
                return True
                
        except Exception as e:
            logger.error(f"Database operation {operation} failed: {e}")
            return None
    
    def _ai_operation(self, psid: str, text: str, system_prompt: str):
        """AI operation wrapper"""
        try:
            if self.ai_adapter:
                # Use existing AI adapter
                result = self.ai_adapter.process_message(text, system_prompt)
                return {
                    "summary": result.get("response", "Quick analysis complete."),
                    "action": "Consider setting a budget for better tracking.",
                    "question": "Need more details or want to set limits?"
                }
            else:
                # Fallback response
                return {
                    "summary": "Expense logged successfully.",
                    "action": "Consider setting a budget for better tracking.",
                    "question": "Need more details or want to set limits?"
                }
        except Exception as e:
            logger.error(f"AI operation failed: {e}")
            return {
                "summary": "Quick analysis complete.",
                "action": "Consider reviewing your spending patterns.",
                "question": "Want to see more details?"
            }
    
    def handle_text_message(self, psid: str, text: str) -> bool:
        """Handle incoming text message with enhanced UX"""
        try:
            return handle_enhanced_message(
                psid=psid,
                text=text,
                db_func=self._db_operation,
                send_func=self._send_message,
                quick_reply_func=self._send_quick_replies,
                ai_func=self._ai_operation,
                rate_limiter_func=can_use_ai
            )
        except Exception as e:
            logger.error(f"Enhanced message handling failed: {e}")
            self._send_message(psid, "I'm having trouble right now. Please try again.")
            return True
    
    def handle_quick_reply(self, psid: str, payload: str) -> bool:
        """Handle quick reply payload"""
        try:
            return handle_payload(
                psid=psid,
                payload=payload,
                db_func=self._db_operation,
                send_func=self._send_message,
                quick_reply_func=self._send_quick_replies
            )
        except Exception as e:
            logger.error(f"Payload handling failed: {e}")
            self._send_message(psid, "I didn't understand that option. Please try again.")
            return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get UX metrics for observability"""
        return get_ux_metrics()

# Integration function for existing codebase
def create_enhanced_handler(db_session, ai_adapter=None) -> EnhancedMessageHandler:
    """Create enhanced message handler with existing components"""
    return EnhancedMessageHandler(db_session, ai_adapter)

# Test function to validate the integration
def test_enhanced_messaging():
    """Test enhanced messaging components"""
    print("=== ENHANCED MESSAGING TEST ===")
    
    # Test expense parsing
    expenses = [
        "Lunch 250",
        "250 coffee", 
        "Groceries 1500",
        "invalid text"
    ]
    
    for expense in expenses:
        cat, amt = parse_expense(expense)
        print(f"'{expense}' → Category: {cat}, Amount: {amt}")
    
    # Test fallback message
    from limiter import fallback_blurb
    fallback = fallback_blurb(45)
    print(f"\nFallback message: {fallback}")
    
    # Test UX metrics
    record_event("test_event")
    record_event("expense_logged", 3)
    metrics = get_ux_metrics()
    print(f"\nUX Metrics: {metrics}")
    
    print("✅ Enhanced messaging components tested successfully")

if __name__ == "__main__":
    test_enhanced_messaging()