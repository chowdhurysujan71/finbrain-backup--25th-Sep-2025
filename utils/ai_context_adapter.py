"""
AI Context Adapter - Integrates context packets with AI responses
Enforces structured output and prevents generic advice when data is insufficient
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from utils.context_packet import (
    build_context, is_context_thin, get_thin_context_reply,
    format_context_for_ai, CONTEXT_SYSTEM_PROMPT, RESPONSE_SCHEMA
)
from utils.ux_components import format_coach_reply, safe_send_text, record_event

logger = logging.getLogger(__name__)

class ContextDrivenAI:
    """AI adapter that enforces context-driven responses with guard logic"""
    
    def __init__(self, ai_adapter, db_session):
        self.ai_adapter = ai_adapter
        self.db = db_session
        
    def process_with_context(self, psid: str, user_text: str) -> Dict[str, Any]:
        """
        Process user message with context packet and structured response
        
        Args:
            psid: Facebook Page-Scoped ID
            user_text: User's message
            
        Returns:
            Dict with response type, text, and metadata
        """
        try:
            # Build user context packet
            context = build_context(psid, self.db)
            record_event("context_packet_built")
            
            # Check if context is too thin for personalized advice
            if is_context_thin(context):
                message, quick_replies = get_thin_context_reply()
                record_event("context_thin_guard_triggered")
                
                return {
                    "type": "thin_context",
                    "message": message,
                    "quick_replies": quick_replies,
                    "context_quality": "thin",
                    "categories_count": len(context["top_cats"]),
                    "total_spend": context["total_spend_30d"]
                }
            
            # Context is rich enough - proceed with AI
            ai_context = format_context_for_ai(context)
            
            # Prepare messages for AI with context
            messages = [
                {"role": "system", "content": CONTEXT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {user_text}\n\n{ai_context}"}
            ]
            
            # Call AI with structured response schema
            ai_response = self._call_ai_with_schema(messages)
            
            if ai_response:
                # Format the structured response
                formatted_text = format_coach_reply(
                    ai_response["summary"],
                    ai_response["action"], 
                    ai_response["question"]
                )
                
                record_event("context_driven_ai_success")
                
                return {
                    "type": "ai_response",
                    "message": formatted_text,
                    "quick_replies": [
                        {"title": "Show breakdown", "payload": "SHOW_BREAKDOWN"},
                        {"title": "Set a cap", "payload": "SET_GOAL"},
                        {"title": "Not now", "payload": "IGNORE"}
                    ],
                    "context_quality": "rich",
                    "categories_count": len(context["top_cats"]),
                    "total_spend": context["total_spend_30d"],
                    "ai_components": ai_response
                }
            else:
                # AI failed - fallback to structured non-AI response
                record_event("context_driven_ai_failed")
                return self._generate_fallback_response(context, user_text)
                
        except Exception as e:
            logger.error(f"Context-driven AI processing failed: {e}")
            record_event("context_driven_ai_error")
            
            return {
                "type": "error",
                "message": "I'm having trouble analyzing your spending right now. Please try again.",
                "quick_replies": [
                    {"title": "Log Expense", "payload": "LOG_EXPENSE"},
                    {"title": "Try Again", "payload": "RETRY_ANALYSIS"}
                ]
            }
    
    def _call_ai_with_schema(self, messages: list) -> Optional[Dict[str, str]]:
        """
        Call AI with JSON schema enforcement
        
        Args:
            messages: List of message objects for AI
            
        Returns:
            Dict with summary/action/question or None if failed
        """
        try:
            # Use existing AI adapter with schema enforcement
            if hasattr(self.ai_adapter, 'process_with_schema'):
                result = self.ai_adapter.process_with_schema(
                    messages=messages,
                    response_schema=RESPONSE_SCHEMA
                )
            else:
                # Fallback for existing adapters without schema support
                result = self.ai_adapter.process_message(
                    user_message=messages[-1]["content"],
                    system_prompt=messages[0]["content"]
                )
                
                # Try to parse as JSON if it's a string
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        # Structure the response manually
                        result = {
                            "summary": result[:100] + "..." if len(result) > 100 else result,
                            "action": "Review your spending patterns for insights.",
                            "question": "Want to see more details?"
                        }
            
            # Validate required fields
            if isinstance(result, dict) and all(key in result for key in ["summary", "action", "question"]):
                return result
            else:
                logger.warning(f"AI response missing required fields: {result}")
                return None
                
        except Exception as e:
            logger.error(f"AI schema call failed: {e}")
            return None
    
    def _generate_fallback_response(self, context: Dict[str, Any], user_text: str) -> Dict[str, Any]:
        """
        Generate structured fallback response using context data
        
        Args:
            context: User context packet
            user_text: Original user message
            
        Returns:
            Structured response dict
        """
        try:
            top_cat = context["top_cats"][0] if context["top_cats"] else None
            total_spend = context["total_spend_30d"]
            
            if top_cat:
                category = top_cat["category"]
                amount = top_cat["amount"]
                delta = top_cat["delta_pct"]
                
                summary = f"{category.title()} is ৳{amount:,} in 30d, {delta:+d}% vs prior. Total spend: ৳{total_spend:,}."
                action = f"Consider setting a {category} budget or reviewing top transactions."
                question = f"Want to see your {category} breakdown or set a spending cap?"
            else:
                summary = f"Total spend is ৳{total_spend:,} in the last 30 days."
                action = "Track your spending by category for better insights."
                question = "Want to log recent expenses or see spending trends?"
            
            formatted_text = format_coach_reply(summary, action, question)
            
            return {
                "type": "fallback_structured",
                "message": formatted_text,
                "quick_replies": [
                    {"title": "Show categories", "payload": "SHOW_CATEGORIES"},
                    {"title": "Set budget", "payload": "SET_GOAL"},
                    {"title": "Log expense", "payload": "LOG_EXPENSE"}
                ],
                "context_quality": "rich",
                "categories_count": len(context["top_cats"]),
                "total_spend": total_spend
            }
            
        except Exception as e:
            logger.error(f"Fallback response generation failed: {e}")
            return {
                "type": "error",
                "message": "Unable to analyze your spending right now.",
                "quick_replies": [{"title": "Try again", "payload": "RETRY_ANALYSIS"}]
            }

def handle_context_driven_message(psid: str, text: str, db_session, ai_adapter, 
                                 send_func, quick_reply_func, rate_limiter_func) -> bool:
    """
    Main handler for context-driven messaging with guard logic
    
    Args:
        psid: Facebook Page-Scoped ID
        text: User message
        db_session: Database session
        ai_adapter: AI processing adapter
        send_func: Function to send messages
        quick_reply_func: Function to send quick replies
        rate_limiter_func: Rate limiting function
        
    Returns:
        True if message was handled
    """
    try:
        # Check rate limiting first
        allowed, retry_in = rate_limiter_func(psid)
        if not allowed:
            from limiter import fallback_blurb
            safe_send_text(send_func, psid, fallback_blurb(retry_in))
            quick_reply_func(psid, [
                {"title": "Log Expense", "payload": "LOG_EXPENSE"},
                {"title": "Weekly Review", "payload": "WEEKLY_REVIEW"},
                {"title": "Set Goal", "payload": "SET_GOAL"}
            ])
            record_event("rate_limited_with_context")
            return True
        
        # Process with context-driven AI
        context_ai = ContextDrivenAI(ai_adapter, db_session)
        response = context_ai.process_with_context(psid, text)
        
        # Send response based on type
        safe_send_text(send_func, psid, response["message"])
        
        if "quick_replies" in response:
            quick_reply_func(psid, response["quick_replies"])
        
        # Log metrics
        record_event(f"context_response:{response['type']}")
        if "categories_count" in response:
            record_event("context_categories", response["categories_count"])
        if "total_spend" in response:
            record_event("context_total_spend", int(response["total_spend"]))
        
        logger.info(f"Context-driven response for {psid[:8]}...: {response['type']}")
        return True
        
    except Exception as e:
        logger.error(f"Context-driven message handling failed: {e}")
        safe_send_text(send_func, psid, "I'm having trouble right now. Please try again.")
        record_event("context_handler_error")
        return True

# Test function
def test_context_driven_ai():
    """Test context-driven AI system"""
    print("=== CONTEXT-DRIVEN AI TEST ===")
    
    # Test thin context detection
    print("\n1. Thin Context Test:")
    thin_context = {
        "income_30d": 0,
        "top_cats": [],
        "total_spend_30d": 0,
        "recurring": [],
        "goals": [],
        "context_quality": "thin"
    }
    
    print(f"   Context is thin: {is_context_thin(thin_context)}")
    message, replies = get_thin_context_reply()
    print(f"   Guard message: {message}")
    print(f"   Quick replies: {[r['title'] for r in replies]}")
    
    # Test rich context formatting
    print("\n2. Rich Context Test:")
    rich_context = {
        "income_30d": 55000,
        "top_cats": [
            {"category": "dining", "amount": 8240, "delta_pct": 18},
            {"category": "groceries", "amount": 12500, "delta_pct": -5}
        ],
        "total_spend_30d": 42600,
        "recurring": [{"name": "rent", "amount": 15000, "day": 1}],
        "goals": [{"name": "emergency", "current": 25000, "target": 100000}],
        "context_quality": "rich"
    }
    
    print(f"   Context is thin: {is_context_thin(rich_context)}")
    ai_format = format_context_for_ai(rich_context)
    print(f"   AI format: {ai_format[:150]}...")
    
    # Test schema structure
    print("\n3. Response Schema Test:")
    print(f"   Required fields: {RESPONSE_SCHEMA['required']}")
    print(f"   Summary type: {RESPONSE_SCHEMA['properties']['summary']['type']}")
    
    print("\n✅ Context-driven AI system tested successfully")

if __name__ == "__main__":
    test_context_driven_ai()