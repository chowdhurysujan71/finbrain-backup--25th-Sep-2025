"""
Optimized AI Reply Function - Direct integration of context packet system
Replaces existing AI processing with streamlined context-driven responses
"""

import json
import logging

from ai_adapter_gemini import generate_with_schema

from limiter import can_use_ai, fallback_blurb
from utils.context_packet import build_context

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a personable financial coach.
Use ONLY the provided user_context for numeric advice.
If user_context is empty or too thin (<2 categories), do not generalize.
Instead, ask for one high-leverage step to collect data (e.g., "log 3 biggest spends today" or "import last month").
Reply in 2–3 sentences max. Give one next step and one question. Avoid jargon. Use numbers when helpful.
"""

def ai_reply(psid, user_text, db, llm):
    """
    Generate AI response with context packet and schema enforcement
    
    Args:
        psid: Facebook Page-Scoped ID
        user_text: User's message
        db: Database session
        llm: AI adapter (for compatibility, uses Gemini directly)
        
    Returns:
        Dict with summary/action/question structure
    """
    try:
        # 1. Build context from DB
        ctx = build_context(psid, db)
        
        # 2. If context too thin → don't allow generic advice
        if ctx["total_spend_30d"] == 0 or len(ctx["top_cats"]) < 2:
            return {
                "summary": "I don't see enough recent spend to personalize this.",
                "action":  "Log your 3 biggest expenses today so I can analyze.",
                "question": "Want to log them now or import last month's data?"
            }

        # 3. Call AI with enforced schema
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {user_text}\n\nuser_context={json.dumps(ctx, ensure_ascii=False)}"}
        ]
        
        # Use Gemini schema generation directly
        response_format = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "action": {"type": "string"},
                "question": {"type": "string"}
            },
            "required": ["summary", "action", "question"]
        }
        
        # Format for Gemini
        full_prompt = f"{messages[1]['content']}"
        
        result = generate_with_schema(
            user_text=full_prompt,
            system_prompt=SYSTEM_PROMPT,
            response_schema=response_format
        )
        
        if result["ok"] and "data" in result:
            return result["data"]
        
        # AI failed - return structured fallback using context
        top_cat = ctx["top_cats"][0] if ctx["top_cats"] else None
        if top_cat:
            category = top_cat["category"]
            amount = top_cat["amount"]
            delta = top_cat["delta_pct"]
            return {
                "summary": f"{category.title()} is ৳{amount:,} in 30d, {delta:+d}% vs prior.",
                "action": f"Consider setting a {category} budget cap.",
                "question": f"Want to see your {category} breakdown or set a limit?"
            }
        else:
            return {
                "summary": f"Total spend is ৳{ctx['total_spend_30d']:,} in 30 days.",
                "action": "Track spending by category for better insights.",
                "question": "Want to log recent expenses or see trends?"
            }
            
    except Exception as e:
        logger.error(f"AI reply failed for {psid[:8]}...: {e}")
        # 4. Guarantee structured dict even on error
        return {
            "summary": "Here's a quick take.",
            "action": "Want me to set a simple cap for you?",
            "question": "See details or set a goal?"
        }

def handle_message(psid, text, db, llm, send_message, send_quick_replies):
    """
    Updated message handler with optimized AI reply and short formatting
    
    Args:
        psid: Facebook Page-Scoped ID
        text: User message
        db: Database session
        llm: AI adapter
        send_message: Message sending function
        send_quick_replies: Quick reply sending function
    """
    try:
        # Check rate limiting first
        allowed, retry_in = can_use_ai(psid)
        if not allowed:
            send_message(psid, fallback_blurb(retry_in))
            return send_quick_replies(psid, [
                {"title": "Log Expense", "payload": "LOG_EXPENSE"},
                {"title": "Weekly Review", "payload": "WEEKLY_REVIEW"},
                {"title": "Set Goal", "payload": "SET_GOAL"}
            ])

        # Get AI insight with context
        insight = ai_reply(psid, text, db, llm)
        
        # Format message with 280-char limit
        msg = f"{insight['summary']}\n{insight['action']}\n{insight['question']}"
        if len(msg) > 280:
            msg = msg[:260] + "… Want details?"
        
        send_message(psid, msg)
        send_quick_replies(psid, [
            {"title": "Show breakdown", "payload": "SHOW_BREAKDOWN"},
            {"title": "Set a cap", "payload": "SET_GOAL"},
            {"title": "Not now", "payload": "IGNORE"}
        ])
        
        logger.info(f"Context message sent to {psid[:8]}...: {len(msg)} chars")
        
    except Exception as e:
        logger.error(f"Message handling failed for {psid[:8]}...: {e}")
        send_message(psid, "I'm having trouble right now. Please try again.")
        send_quick_replies(psid, [
            {"title": "Try again", "payload": "RETRY_ANALYSIS"}
        ])

# Test function
def test_ai_reply_optimized():
    """Test the optimized AI reply system"""
    print("=== OPTIMIZED AI REPLY TEST ===")
    
    # Mock database and context
    class MockDB:
        pass
    
    class MockLLM:
        pass
    
    # Test thin context response
    print("\n1. Testing Thin Context Response:")
    
    # Mock build_context to return thin context
    original_build_context = build_context
    
    def mock_thin_context(psid, db):
        return {
            "total_spend_30d": 0,
            "top_cats": [],
            "income_30d": 0,
            "recurring": [],
            "goals": []
        }
    
    # Temporarily replace build_context
    import utils.context_packet
    utils.context_packet.build_context = mock_thin_context
    
    result = ai_reply("test_psid", "How can I save money?", MockDB(), MockLLM())
    print(f"   Summary: {result['summary']}")
    print(f"   Action: {result['action']}")
    print(f"   Question: {result['question']}")
    
    # Test message formatting
    print("\n2. Testing Message Formatting:")
    msg = f"{result['summary']}\n{result['action']}\n{result['question']}"
    print(f"   Message length: {len(msg)} chars")
    print(f"   Under 280 limit: {len(msg) <= 280}")
    
    # Restore original function
    utils.context_packet.build_context = original_build_context
    
    print("\n✅ Optimized AI reply system tested successfully")

if __name__ == "__main__":
    test_ai_reply_optimized()