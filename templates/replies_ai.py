"""
AI Reply Templates for FinBrain
Natural, coach-style responses that sound conversational and helpful
"""

import logging
from decimal import Decimal
from typing import Optional, List, Dict, Any

logger = logging.getLogger("templates.replies_ai")

def select_reply_pack() -> str:
    """
    Always returns AI reply pack - no flags, always-on AI responses.
    
    Returns:
        Always "AI" - feature flags removed for production stability
    """
    return "AI"

def log_reply_banner(intent: str, psid_hash: str):
    """Log reply pack selection banner"""
    pack = select_reply_pack()
    logger.info(f"[REPLY] pack={pack} intent={intent} psid={psid_hash[:8]}...")

# AI Expense Logging Templates
def format_ai_single_expense_reply(amount: float, category: str, currency: str = "BDT") -> str:
    """AI-style reply for single expense logging"""
    currency_symbol = {
        'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'
    }.get(currency, currency)
    
    variations = [
        f"✅ Got it! Logged {currency_symbol}{amount:.0f} for {category}.",
        f"Perfect! Added {currency_symbol}{amount:.0f} to your {category} expenses.",
        f"Done! {currency_symbol}{amount:.0f} for {category} is saved.",
        f"✅ Noted: {currency_symbol}{amount:.0f} spent on {category}."
    ]
    
    # Use amount as seed for consistent variation selection
    return variations[int(amount) % len(variations)]

def format_ai_multi_expense_reply(expenses: List[Dict[str, Any]], total_amount: float) -> str:
    """AI-style reply for multiple expense logging"""
    if len(expenses) <= 1:
        return format_ai_single_expense_reply(expenses[0]['amount'], expenses[0]['category'])
    
    expense_list = "; ".join([f"৳{exp['amount']:.0f} {exp['category']}" for exp in expenses])
    
    variations = [
        f"✅ Logged: {expense_list}. Total: ৳{total_amount:.0f}",
        f"Got all of them! {expense_list} (৳{total_amount:.0f} total)",
        f"Perfect! Saved {len(expenses)} expenses: {expense_list}",
        f"✅ Done: {expense_list}. Running total: ৳{total_amount:.0f}"
    ]
    
    return variations[len(expenses) % len(variations)]

# AI Summary Templates  
def format_ai_summary_reply(period: str, total_amount: float, total_entries: int, 
                           categories: Optional[List[str]] = None) -> str:
    """AI-style summary with coaching tone"""
    
    if total_amount == 0:
        return f"📊 No expenses tracked this {period.lower()} yet. Ready to start logging?"
    
    # Main summary
    summary = f"📊 This {period.lower()}: ৳{total_amount:.0f} across {total_entries} expense"
    if total_entries != 1:
        summary += "s"
    summary += "."
    
    # Add categories if available
    if categories and len(categories) > 0:
        if len(categories) <= 3:
            cat_text = ", ".join(categories)
            summary += f" Main areas: {cat_text}."
        else:
            summary += f" Spending across {len(categories)} categories."
    
    # Add coaching insights
    if total_amount > 5000:
        summary += "\n\n💡 Heavy spending period - want insights to optimize?"
    elif total_amount > 2000:
        summary += "\n\n📈 Solid tracking! Type 'insight' for spending analysis."
    else:
        summary += "\n\n✅ Great job staying mindful of your spending!"
    
    return summary

# AI Insight Templates
def format_ai_insight_reply(insights: List[str], total_amount: Optional[float] = None) -> str:
    """AI-style insights with personalized coaching"""
    
    if not insights:
        return ("🎯 Your spending looks balanced! You're doing well with tracking expenses. "
                "Keep it up and consider setting monthly goals for even better control.")
    
    insight_text = "💡 Here's what I noticed:\n" + "\n".join(f"• {insight}" for insight in insights)
    
    # Add encouraging coaching
    if total_amount and total_amount > 3000:
        insight_text += "\n\n🚀 Small changes can make a big difference. Which area feels easiest to start with?"
    else:
        insight_text += "\n\n✨ You're building great financial awareness!"
    
    return insight_text

# AI Correction Templates  
def format_ai_corrected_reply(old_amount: float, old_currency: str, new_amount: Decimal, 
                             new_currency: str, category: str, merchant: Optional[str] = None) -> str:
    """AI-style correction confirmation"""
    old_symbol = {'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'}.get(old_currency, old_currency)
    new_symbol = {'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'}.get(new_currency, new_currency)
    
    merchant_part = f" at {merchant}" if merchant else ""
    
    variations = [
        f"✅ Corrected: {old_symbol}{old_amount} → {new_symbol}{new_amount} for {category}{merchant_part}",
        f"Fixed! Updated from {old_symbol}{old_amount} to {new_symbol}{new_amount} for {category}{merchant_part}",
        f"Got it! Changed {category} expense: {old_symbol}{old_amount} → {new_symbol}{new_amount}{merchant_part}",
        f"✅ Updated: {category} expense now {new_symbol}{new_amount} (was {old_symbol}{old_amount}){merchant_part}"
    ]
    
    return variations[int(float(new_amount)) % len(variations)]

def format_ai_correction_no_candidate_reply(amount: Decimal, currency: str, category: str) -> str:
    """AI-style reply when no correction candidate found"""
    currency_symbol = {'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'}.get(currency, currency)
    
    variations = [
        f"No recent {category} expense to correct, so I logged {currency_symbol}{amount} as a new entry! ✅",
        f"Couldn't find a recent match, so added {currency_symbol}{amount} for {category} as new 📝",
        f"I'll log {currency_symbol}{amount} for {category} as a fresh expense since I didn't find a recent one to correct."
    ]
    
    return variations[int(float(amount)) % len(variations)]

def format_ai_correction_duplicate_reply() -> str:
    """AI-style duplicate correction message"""
    variations = [
        "I've already processed that correction. Anything else to update?",
        "That correction is already done! Need to fix something else?",
        "Already handled that change. What else can I help with?"
    ]
    
    import time
    return variations[int(time.time()) % len(variations)]

# Generic AI Error Templates
def format_ai_error_reply(context: str = "general") -> str:
    """AI-style error responses"""
    if context == "correction":
        return "I couldn't process that correction. Could you try rephrasing or logging it as a new expense?"
    elif context == "logging":
        return "Hmm, I couldn't log that expense. Could you try something like '100 for lunch'?"
    else:
        return "Something went wrong on my end. Please try again!"

def format_ai_help_reply() -> str:
    """AI-style help message"""
    return ("I can help you track expenses! Try:\n"
            "💰 'coffee 50' or 'lunch 200' - to log expenses\n" 
            "📊 'summary' - to see your spending\n"
            "💡 'insight' - for personalized tips\n"
            "✏️ 'sorry, I meant 300' - to correct mistakes")

def format_ai_duplicate_reply() -> str:
    """AI-style duplicate expense message"""
    variations = [
        "I've already logged that expense! Anything else to track?",
        "That one's already saved. What else did you spend on?",
        "Already got that expense recorded! ✅"
    ]
    
    import time
    return variations[int(time.time()) % len(variations)]

# Utility function to remove any debug footers
def clean_ai_reply(text: str) -> str:
    """Remove any debug footers from AI replies"""
    # Remove any lines starting with "pong |" or containing "mode="
    lines = text.split('\n')
    clean_lines = [line for line in lines if not (line.strip().startswith('pong |') or 'mode=' in line)]
    return '\n'.join(clean_lines).strip()

# Coaching Flow Templates
def coach_focus(topic_suggestions: List[str]) -> Dict[str, Any]:
    """Generate focus question for coaching flow"""
    suggestions_text = ", ".join(topic_suggestions[:-1]) + f" or {topic_suggestions[-1]}" if len(topic_suggestions) > 1 else topic_suggestions[0]
    
    text = f"Which area do you want to improve first—{suggestions_text}? 🎯"
    
    quick_replies = [{'title': topic.title(), 'payload': f'COACH_{topic.upper()}'} for topic in topic_suggestions]
    quick_replies.append({'title': 'Skip', 'payload': 'COACH_SKIP'})
    
    return {
        'text': text,
        'intent': 'coaching',
        'category': None,
        'amount': None,
        'quick_replies': quick_replies
    }

def coach_commit(topic: str, action_options: List[str]) -> Dict[str, Any]:
    """Generate commitment question for coaching flow"""
    options_text = " or ".join(action_options)
    
    text = f"Nice choice! Let's try one small step: {options_text}. Which sounds doable this week? 💪"
    
    quick_replies = [{'title': option.title(), 'payload': f'COACH_{option.upper().replace(" ", "_")}'} for option in action_options]
    quick_replies.extend([
        {'title': 'Something Else', 'payload': 'COACH_OTHER'},
        {'title': 'Skip', 'payload': 'COACH_SKIP'}
    ])
    
    return {
        'text': text,
        'intent': 'coaching',
        'category': None,
        'amount': None,
        'quick_replies': quick_replies
    }

def coach_done(action: str) -> Dict[str, Any]:
    """Generate completion message for coaching flow"""
    variations = [
        f"💪 Perfect! I'll check back in a few days to see how {action} is going.",
        f"🌟 Great choice! {action.title()} is a solid step forward.",
        f"✨ Awesome! {action.title()} will make a real difference."
    ]
    
    # Use action length as seed for variation
    text = variations[len(action) % len(variations)]
    text += " Type 'summary' anytime to track your progress!"
    
    return {
        'text': text,
        'intent': 'coaching_complete',
        'category': None,
        'amount': None
    }