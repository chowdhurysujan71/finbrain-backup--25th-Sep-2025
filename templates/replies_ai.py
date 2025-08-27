"""
AI Reply Templates for finbrain
Natural, coach-style responses that sound conversational and helpful
"""

import logging
import random
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
    """AI-style reply for single expense logging with natural language variation"""
    import random
    
    currency_symbol = {
        'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'
    }.get(currency, currency)
    
    # Main confirmation variations
    base_variations = [
        f"✅ Got it! Logged {currency_symbol}{amount:.0f} for {category}",
        f"Perfect! Added {currency_symbol}{amount:.0f} to your {category} expenses",
        f"Done! {currency_symbol}{amount:.0f} for {category} is saved",
        f"✅ Noted: {currency_symbol}{amount:.0f} spent on {category}",
        f"All set! {currency_symbol}{amount:.0f} {category} recorded",
        f"Tracked! {currency_symbol}{amount:.0f} {category} expense saved"
    ]
    
    # Friendly closings that vary naturally
    closings = [
        ". Keep tracking! 💪",
        ". Thanks for staying on top of your expenses!",
        ". Great job keeping records! 📊",
        ". Your financial awareness is awesome! 🌟", 
        ". Keep up the excellent tracking!",
        ". Nice work staying organized! ✨",
        ". Thanks for the update!",
        ". Way to stay mindful of spending!",
        ". Your budget thanks you! 💚"
    ]
    
    base_response = random.choice(base_variations)
    closing = random.choice(closings)
    
    return f"{base_response}{closing}"

def format_ai_multi_expense_reply(expenses: List[Dict[str, Any]], total_amount: float) -> str:
    """AI-style reply for multiple expense logging with natural variation"""
    import random
    
    if len(expenses) <= 1:
        return format_ai_single_expense_reply(expenses[0]['amount'], expenses[0]['category'])
    
    expense_list = "; ".join([f"৳{exp['amount']:.0f} {exp['category']}" for exp in expenses])
    
    base_variations = [
        f"✅ Logged: {expense_list}. Total: ৳{total_amount:.0f}",
        f"Got all of them! {expense_list} (৳{total_amount:.0f} total)",
        f"Perfect! Saved {len(expenses)} expenses: {expense_list}",
        f"✅ Done: {expense_list}. Running total: ৳{total_amount:.0f}",
        f"All tracked! {expense_list} - ৳{total_amount:.0f} total",
        f"Excellent! {len(expenses)} expenses saved: {expense_list}"
    ]
    
    # Friendly closings for multi-expense
    closings = [
        " Great expense discipline! 🎯",
        " Thanks for the detailed tracking!",
        " Your organization skills are impressive! ⭐",
        " Keep up this excellent habit!",
        " Amazing expense awareness! 💪"
    ]
    
    base_response = random.choice(base_variations)
    closing = random.choice(closings)
    
    return f"{base_response}{closing}"

# AI Summary Templates  
def format_ai_summary_reply(period: str, total_amount: float, total_entries: int, 
                           categories: Optional[List[str]] = None) -> str:
    """AI-style summary with coaching tone and natural variation"""
    import random
    
    # Make timeframes more explicit and clear
    timeframe_map = {
        "last 7 days": "Last 7 Days",
        "this month": "This Month", 
        "month": "This Month",
        "week": "Last 7 Days"
    }
    
    display_period = timeframe_map.get(period.lower(), period.title())
    
    if total_amount == 0:
        no_data_responses = [
            f"📊 No expenses tracked in {display_period} yet. Ready to start logging?",
            f"📊 Clean slate for {display_period}! Time to track some expenses?",
            f"📊 Nothing logged in {display_period} - let's get started!",
            f"📊 Fresh start for {display_period}! Ready to track your spending?"
        ]
        return random.choice(no_data_responses)
    
    # Main summary with clear timeframe variations
    summary_templates = [
        f"📊 {display_period}: ৳{total_amount:.0f} across {total_entries} expense",
        f"📊 {display_period} Summary: ৳{total_amount:.0f} in {total_entries} transaction",
        f"📊 Your {display_period}: ৳{total_amount:.0f} over {total_entries} expense",
        f"📊 {display_period} Recap: ৳{total_amount:.0f} across {total_entries} entry"
    ]
    
    summary = random.choice(summary_templates)
    if total_entries != 1:
        summary += "s"
    
    # Add category information (avoiding duplication)
    if categories and len(categories) > 0:
        if len(categories) <= 3:
            cat_text = ", ".join(categories)
            summary += f". Main areas: {cat_text}."
        else:
            summary += f". Spending across {len(categories)} categories."
    else:
        summary += "."
    
    
    # Add coaching insights with natural variation
    if total_amount > 5000:
        coaching_tips = [
            "\n\n💡 Heavy spending period - want insights to optimize?",
            "\n\n💡 That's quite a bit - interested in some tips to trim costs?",
            "\n\n📊 Big spending month - let me know if you want analysis!"
        ]
        summary += random.choice(coaching_tips)
    elif total_amount > 2000:
        medium_tips = [
            "\n\n📈 Solid tracking! Type 'insight' for spending analysis.",
            "\n\n📊 Nice spending discipline! Want deeper insights?",
            "\n\n💪 Good financial awareness - need any optimization tips?"
        ]
        summary += random.choice(medium_tips)
    else:
        positive_tips = [
            "\n\n✅ Great job staying mindful of your spending!",
            "\n\n🌟 Excellent expense control - keep it up!",
            "\n\n💚 Love your spending discipline!"
        ]
        summary += random.choice(positive_tips)
    
    # Add friendly "check back again" closings that vary naturally
    friendly_closings = [
        " Feel free to check back anytime! 😊",
        " Check back again soon for updates!",
        " Hope that helps - come back anytime!",
        " Always here when you need spending insights!",
        " Thanks for staying on top of your finances!",
        " Keep up the great work and check in again soon!",
        " Your financial awareness is impressive - see you next time!",
        " Thanks for tracking with me - until next time! 🚀"
    ]
    
    summary += random.choice(friendly_closings)
    
    return summary

# AI Insight Templates
def format_ai_insight_reply(insights: List[str], total_amount: Optional[float] = None, timeframe: str = "this month") -> str:
    """AI-style insights with personalized coaching and user acknowledgment"""
    
    # Make timeframe explicit in insights
    timeframe_display = {
        "this month": "This Month",
        "last 7 days": "Last 7 Days", 
        "month": "This Month",
        "week": "Last 7 Days"
    }.get(timeframe.lower(), timeframe.title())
    
    # User-acknowledgment line prepended
    if not insights:
        return (f"You asked for an analysis. Here's a quick read on your {timeframe_display.lower()} spending...\n\n"
                "🎯 Your spending looks balanced! You're doing well with tracking expenses. "
                "Keep it up and consider setting monthly goals for even better control.")
    
    insight_text = f"You asked for an analysis. Here's a quick read on your {timeframe_display.lower()} spending...\n\n💡 Here's what I noticed ({timeframe_display}):\n" + "\n".join(f"• {insight}" for insight in insights)
    
    # Add encouraging coaching with friendly closings
    if total_amount and total_amount > 3000:
        insight_closings = [
            "\n\n🚀 Small changes can make a big difference. Which area feels easiest to start with?",
            "\n\n💡 Want to tackle any of these areas? I'm here to help!",
            "\n\n🎯 Ready to optimize? Let me know where you'd like to focus!"
        ]
        insight_text += random.choice(insight_closings)
    else:
        positive_closings = [
            "\n\n✨ You're building great financial awareness!",
            "\n\n💪 Your spending discipline is impressive!",
            "\n\n🌟 Keep up this excellent financial mindfulness!"
        ]
        insight_text += random.choice(positive_closings)
    
    # Add natural "check back again" closings
    check_back_closings = [
        " Check back anytime for fresh insights!",
        " Feel free to ask for analysis again soon!",
        " Always here when you need spending guidance!",
        " Come back anytime for more financial insights!",
        " Thanks for staying financially aware - see you next time!"
    ]
    
    insight_text += random.choice(check_back_closings)
    
    return insight_text

# AI Correction Templates  
def format_ai_corrected_reply(old_amount: float, old_currency: str, new_amount: Decimal, 
                             new_currency: str, category: str, merchant: Optional[str] = None) -> str:
    """AI-style correction confirmation"""
    old_symbol = {'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'}.get(old_currency, old_currency)
    new_symbol = {'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'}.get(new_currency, new_currency)
    
    merchant_part = f" at {merchant}" if merchant else ""
    
    base_variations = [
        f"✅ Corrected: {old_symbol}{old_amount} → {new_symbol}{new_amount} for {category}{merchant_part}",
        f"Fixed! Updated from {old_symbol}{old_amount} to {new_symbol}{new_amount} for {category}{merchant_part}",
        f"Got it! Changed {category} expense: {old_symbol}{old_amount} → {new_symbol}{new_amount}{merchant_part}",
        f"✅ Updated: {category} expense now {new_symbol}{new_amount} (was {old_symbol}{old_amount}){merchant_part}"
    ]
    
    friendly_endings = [
        " Thanks for keeping your records accurate!",
        " Great attention to detail!",
        " Love the precision! 📊",
        " Perfect - accuracy matters!",
        " Nice catch on that correction!"
    ]
    
    import random
    base = random.choice(base_variations)
    ending = random.choice(friendly_endings)
    
    return f"{base}{ending}"

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