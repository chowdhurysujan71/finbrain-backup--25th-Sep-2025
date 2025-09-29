# utils/faq_map.py
import re
from typing import Optional

FAQ_JSON = {
    "faq": {
        "what is finbrain": (
            "I'm your personal finance buddy! 🤖 I help you track spending through simple conversations - "
            "just tell me what you bought and I'll handle the rest. Think expense tracking made as easy as texting a friend!"
        ),
        "how does expense tracking work": (
            "Super simple! Just tell me what you spent - like '500 taka for lunch' or 'bought groceries 2000' - "
            "and I'll automatically sort it into the right category. No forms, no hassle! 🧾"
        ),
        "is my financial data secure": (
            "🔒 Your data is encrypted **in transit and at rest**. We don't store sensitive banking details and follow "
            "industry-standard security practices. View our Privacy Policy: /privacy-policy"
        ),
        "what messaging platforms do you support": (
            "💬 We're starting with popular platforms and expanding based on user demand. Join early access to help shape priorities. "
            "For details and updates check our help section."
        ),
        "how much does finbrain cost": (
            "We're currently in early access - it's free while we perfect the experience! "
            "When we launch, early users like you will get special pricing. Want to try it out? 💰"
        ),
        "can i connect my bank accounts": (
            "Bank connections are in our roadmap! For now, we focus on simple conversation-based tracking - "
            "just tell me what you spent and I'll handle the rest. Much more private this way! 🏦"
        ),
        "what kind of insights can i get": (
            "Great question! I'll show you where your money goes and help you make smarter decisions. "
            "Think personalized spending patterns, budget suggestions, and tips tailored just for you. "
            "Want to see what I can find in your current spending? Just ask for insights! 💡"
        ),
        "how do i get started": (
            "🚀 Join early access with your email and be among the first to experience finbrain. "
            "For details and updates check our help section."
        ),
        "privacy policy and terms": (
            "📋 View our legal documents:\n"
            "• Privacy Policy: /privacy-policy\n"
            "• Terms of Service: /terms-of-service\n"
            "Your privacy and data protection are our top priority.\n\n"
            "⚖️ Important: finbrain provides educational insights only, not professional financial advice. "
            "Always consult qualified financial advisors for investment or major financial decisions."
        )
    },
    "smalltalk": {
        "hi": "👋 Hi there! Want to log an expense, see a summary, or get an insight?",
        "hello": "😊 Hello! I can help you track expenses or show your spending summary.",
        "who built you": (
            "🏗️ I was built by the finbrain team to make managing money as easy as sending a message. "
            "For details and updates check our help section."
        )
    },
    "fallback": {
        "default": (
            "I'm here to help with your money! Want to log an expense, see your spending summary, or get some insights? "
            "Try something like 'spent 500 on groceries' or 'show my summary' 💰"
        )
    }
}

# Keyword coverage (synonyms) for robust matching
INTENT_KEYWORDS = {
    "what is finbrain": [
        "what is finbrain", "tell me about finbrain", "explain finbrain",
        "what do you do", "what can you do", "who are you"
    ],
    "how does expense tracking work": [
        "how does expense tracking", "how do i log", "how to log", "track expenses",
        "record expense", "log expense", "how does logging work"
    ],
    "is my financial data secure": [
        "store my data", "how do you store my data", "how do you store data",
        "is my data safe", "data secure", "data security", "data protection",
        "privacy", "privacy policy", "how is my data stored",
        # Enhanced variations for natural questions
        "do you store my personal data", "do you store personal data", "personal data",
        "financial data", "my personal information", "personal information",
        "data privacy", "safe data", "secure data", "protect my data"
    ],
    "what messaging platforms do you support": [
        "which platforms", "what platforms", "messaging platforms",
        "do you support whatsapp", "messenger support", "platform support"
    ],
    "how much does finbrain cost": [
        "how much does it cost", "pricing", "price", "cost", "is it free", "how much is finbrain"
    ],
    "can i connect my bank accounts": [
        "connect my bank", "bank connection", "bank integration", "link bank", "sync bank",
        # Enhanced variations for natural questions
        "connected with any bank", "connected with bank", "any bank", "which banks",
        "bank accounts", "banking", "financial institutions", "integrate bank",
        "are you connected", "do you connect", "bank support",
        # More specific patterns for "are you connected with any bank"
        "you connected with", "connected", "bank", "banks"
    ],
    "what kind of insights can i get": [
        "what insights", "what tips", "spending insights", "recommendations", "coach", "advice", "what kind of insights"
    ],
    "how do i get started": [
        "how do i get started", "get started", "join early access", "sign up", "how to start"
    ],
    "privacy policy and terms": [
        "privacy policy", "terms of service", "terms", "legal documents", "tos", "privacy",
        "privacy and terms", "view privacy", "show privacy", "terms and conditions",
        "legal", "policy", "show terms", "privacy policy link", "terms link"
    ],
    "hi": ["hi", "hey"],
    "hello": ["hello", "helo", "heloo"],
    "who built you": ["who built you", "who made you", "your creator", "made you"]
}

_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]")

def normalize(text: str) -> str:
    return _NORMALIZE_RE.sub("", text.lower().strip())

def match_faq_or_smalltalk(user_text: str) -> str | None:
    norm = normalize(user_text)
    # Use word boundary matching to avoid false positives like "hi" in "this"
    words = norm.split()
    
    for intent, keywords in INTENT_KEYWORDS.items():
        for k in keywords:
            # For single word keywords, check exact word match
            if " " not in k:
                if k in words:
                    if intent in FAQ_JSON["faq"]:
                        return FAQ_JSON["faq"][intent]
                    if intent in FAQ_JSON["smalltalk"]:
                        return FAQ_JSON["smalltalk"][intent]
            # For multi-word keywords, use substring matching
            else:
                if k in norm:
                    if intent in FAQ_JSON["faq"]:
                        return FAQ_JSON["faq"][intent]
                    if intent in FAQ_JSON["smalltalk"]:
                        return FAQ_JSON["smalltalk"][intent]
    return None

def fallback_default() -> str:
    return FAQ_JSON["fallback"]["default"]