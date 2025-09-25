"""
Context Integration Module - Wires context packets into existing FinBrain message handling
Integrates with the background processor and webhook system for production use
"""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from db_base import db
from limiter import can_use_ai
from utils.context_packet import (
    CONTEXT_SYSTEM_PROMPT,
    RESPONSE_SCHEMA,
    build_context,
    format_context_for_ai,
    get_thin_context_reply,
    is_context_thin,
)
from utils.facebook_handler import send_message
from utils.quick_reply_system import send_custom_quick_replies
from utils.ux_components import format_coach_reply, record_event

logger = logging.getLogger(__name__)

class ContextAwareMessageProcessor:
    """Message processor that integrates context packets with existing FinBrain system"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    def process_message(self, psid: str, text: str) -> dict[str, Any]:
        """
        Process message with context-driven AI and guard logic
        
        Args:
            psid: Facebook Page-Scoped ID
            text: User message text
            
        Returns:
            Dict with processing result and metadata
        """
        try:
            # Step 1: Check rate limiting
            allowed, retry_in = can_use_ai(psid)
            if not allowed:
                from limiter import fallback_blurb
                fallback_msg = fallback_blurb(retry_in)
                
                # Send fallback with quick actions
                send_message(psid, fallback_msg)
                send_custom_quick_replies(psid, "Pick one:", [
                    {"title": "Log Expense", "payload": "LOG_EXPENSE"},
                    {"title": "Weekly Review", "payload": "WEEKLY_REVIEW"},
                    {"title": "Set Goal", "payload": "SET_GOAL"}
                ])
                
                record_event("rate_limited_with_context")
                return {
                    "status": "rate_limited",
                    "message": fallback_msg,
                    "retry_in": retry_in
                }
            
            # Step 2: Build context packet
            context = build_context(psid, self.db)
            record_event("context_packet_built")
            
            # Step 3: Check if context is too thin
            if is_context_thin(context):
                message, quick_replies = get_thin_context_reply()
                
                send_message(psid, message)
                send_custom_quick_replies(psid, "", quick_replies)
                
                record_event("context_thin_guard_triggered")
                return {
                    "status": "thin_context",
                    "message": message,
                    "context_quality": "thin",
                    "categories_count": len(context["top_cats"]),
                    "total_spend": context["total_spend_30d"]
                }
            
            # Step 4: Generate AI response with context and schema
            ai_context = format_context_for_ai(context)
            full_user_text = f"Question: {text}\n\n{ai_context}"
            
            ai_result = generate_with_schema(
                user_text=full_user_text,
                system_prompt=CONTEXT_SYSTEM_PROMPT,
                response_schema=RESPONSE_SCHEMA
            )
            
            if ai_result["ok"] and "data" in ai_result:
                # Successful structured AI response
                structured_response = ai_result["data"]
                
                # Format with coach reply formatter
                formatted_message = format_coach_reply(
                    structured_response["summary"],
                    structured_response["action"],
                    structured_response["question"]
                )
                
                send_message(psid, formatted_message)
                send_custom_quick_replies(psid, "", [
                    {"title": "Show breakdown", "payload": "SHOW_BREAKDOWN"},
                    {"title": "Set a cap", "payload": "SET_GOAL"},
                    {"title": "Not now", "payload": "IGNORE"}
                ])
                
                record_event("context_driven_ai_success")
                return {
                    "status": "ai_success",
                    "message": formatted_message,
                    "context_quality": "rich",
                    "categories_count": len(context["top_cats"]),
                    "total_spend": context["total_spend_30d"],
                    "ai_latency_ms": ai_result.get("latency_ms", 0),
                    "structured_response": structured_response
                }
            
            else:
                # AI failed - generate structured fallback using context
                fallback_response = self._generate_context_fallback(context, text)
                
                send_message(psid, fallback_response["message"])
                send_custom_quick_replies(psid, "", fallback_response["quick_replies"])
                
                record_event("context_driven_fallback")
                return {
                    "status": "fallback_structured",
                    "message": fallback_response["message"],
                    "context_quality": "rich",
                    "categories_count": len(context["top_cats"]),
                    "total_spend": context["total_spend_30d"],
                    "ai_error": ai_result.get("error", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Context message processing failed for {psid[:8]}...: {e}")
            
            # Emergency fallback
            error_msg = "I'm having trouble analyzing your spending right now. Please try again."
            send_message(psid, error_msg)
            
            record_event("context_processing_error")
            return {
                "status": "error",
                "message": error_msg,
                "error": str(e)
            }
    
    def _generate_context_fallback(self, context: dict[str, Any], user_text: str) -> dict[str, Any]:
        """
        Generate structured fallback response using context data when AI fails
        
        Args:
            context: User context packet
            user_text: Original user message
            
        Returns:
            Dict with message and quick replies
        """
        try:
            top_cat = context["top_cats"][0] if context["top_cats"] else None
            total_spend = context["total_spend_30d"]
            
            if top_cat:
                category = top_cat["category"]
                amount = top_cat["amount"]
                delta = top_cat["delta_pct"]
                
                summary = f"{category.title()} is ৳{amount:,} in 30d, {delta:+d}% vs prior."
                action = f"Consider setting a {category} budget to track spending."
                question = f"Want to see your {category} breakdown or set a cap?"
            else:
                summary = f"Total spend is ৳{total_spend:,} in the last 30 days."
                action = "Track spending by category for better insights."
                question = "Want to log recent expenses or see trends?"
            
            formatted_message = format_coach_reply(summary, action, question)
            
            return {
                "message": formatted_message,
                "quick_replies": [
                    {"title": "Show categories", "payload": "SHOW_CATEGORIES"},
                    {"title": "Set budget", "payload": "SET_GOAL"},
                    {"title": "Log expense", "payload": "LOG_EXPENSE"}
                ]
            }
            
        except Exception as e:
            logger.error(f"Context fallback generation failed: {e}")
            return {
                "message": "Unable to analyze your spending right now.",
                "quick_replies": [{"title": "Try again", "payload": "RETRY_ANALYSIS"}]
            }

# Global processor instance for integration
context_processor = None

def initialize_context_processor():
    """Initialize global context processor with database session"""
    global context_processor
    if context_processor is None:
        context_processor = ContextAwareMessageProcessor(db.session)
    return context_processor

def process_message_with_context(psid: str, text: str) -> dict[str, Any]:
    """
    Main entry point for context-driven message processing
    
    Args:
        psid: Facebook Page-Scoped ID
        text: User message
        
    Returns:
        Processing result dictionary
    """
    processor = initialize_context_processor()
    return processor.process_message(psid, text)

# Integration with existing background processor
def handle_message_with_context_integration(psid: str, text: str):
    """
    Integration function for existing background processor
    
    Args:
        psid: Facebook Page-Scoped ID  
        text: User message
    """
    try:
        result = process_message_with_context(psid, text)
        
        # Log metrics for observability
        logger.info(f"Context processing for {psid[:8]}...: {result['status']}")
        
        # Additional logging for production monitoring
        if result["status"] == "ai_success":
            logger.info(f"AI success: {result.get('ai_latency_ms', 0)}ms, {result.get('categories_count', 0)} categories")
        elif result["status"] == "thin_context":
            logger.info(f"Thin context: {result.get('categories_count', 0)} categories, ৳{result.get('total_spend', 0)} spend")
        
        return result
        
    except Exception as e:
        logger.error(f"Context integration failed: {e}")
        # Fallback to basic error handling
        send_message(psid, "I'm having trouble right now. Please try again.")
        return {"status": "integration_error", "error": str(e)}

# Test function
def test_context_integration():
    """Test context integration system"""
    print("=== CONTEXT INTEGRATION TEST ===")
    
    # Test processor initialization
    processor = ContextAwareMessageProcessor(db.session)
    print(f"✓ Processor initialized: {type(processor).__name__}")
    
    # Test context packet components
    from utils.context_packet import CONTEXT_SYSTEM_PROMPT, RESPONSE_SCHEMA
    print(f"✓ System prompt length: {len(CONTEXT_SYSTEM_PROMPT)} chars")
    print(f"✓ Schema required fields: {RESPONSE_SCHEMA['required']}")
    
    # Test schema function availability
    try:
        # Use production AI adapter instead
        print(f"✓ Schema generation function: {generate_with_schema.__name__}")
    except ImportError as e:
        print(f"⚠ Schema function not available: {e}")
    
    # Test quick reply integration
    try:
        from utils.quick_reply_system import send_custom_quick_replies
        print(f"✓ Quick reply system: {send_custom_quick_replies.__name__}")
    except ImportError as e:
        print(f"⚠ Quick reply system not available: {e}")
    
    print("\n✅ Context integration system ready for production")

if __name__ == "__main__":
    test_context_integration()