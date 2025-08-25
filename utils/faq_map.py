# utils/faq_map.py
import re
from typing import Optional

FAQ_JSON = {
    "faq": {
        "what is finbrain": (
            "🤖 **finbrain** is your personal finance AI assistant that lives in your favorite messaging apps. "
            "It helps you track expenses, manage budgets, and get financial insights through simple conversations. "
            "For details and updates visit www.finbrain.app"
        ),
        "how does expense tracking work": (
            "🧾 Just send a message like 'I spent $23 on lunch' and finbrain automatically categorizes and logs your expense. "
            "No apps or forms needed. For details and updates visit www.finbrain.app"
        ),
        "is my financial data secure": (
            "🔒 Your data is encrypted **in transit and at rest**. We don't store sensitive banking details and follow "
            "industry-standard security practices. For details and updates visit www.finbrain.app"
        ),
        "what messaging platforms do you support": (
            "💬 We're starting with popular platforms and expanding based on user demand. Join early access to help shape priorities. "
            "For details and updates visit www.finbrain.app"
        ),
        "how much does finbrain cost": (
            "💸 We're in **early access**. Pricing will be announced before general availability, with special consideration for early users. "
            "For details and updates visit www.finbrain.app"
        ),
        "can i connect my bank accounts": (
            "🏦 Bank integration is planned for future releases. Right now, finbrain focuses on **conversational expense tracking** for maximum privacy. "
            "For details and updates visit www.finbrain.app"
        ),
        "what kind of insights can i get": (
            "💡 You'll see spending analysis, budget alerts, category breakdowns, trends, and **personalized recommendations** to improve decisions. "
            "For details and updates visit www.finbrain.app"
        ),
        "how do i get started": (
            "🚀 Join early access with your email and be among the first to experience finbrain. "
            "For details and updates visit www.finbrain.app"
        )
    },
    "smalltalk": {
        "hi": "👋 Hi there! Want to log an expense, see a summary, or get an insight?",
        "hello": "😊 Hello! I can help you track expenses or show your spending summary.",
        "who built you": (
            "🏗️ I was built by the finbrain team to make managing money as easy as sending a message. "
            "For details and updates visit www.finbrain.app"
        )
    },
    "fallback": {
        "default": (
            "🧭 I can help you track expenses, show summaries, or give insights.\n"
            "Try: *\"spent 100 on lunch\"* or *\"summary this week\"*. "
            "For details and updates visit www.finbrain.app"
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
    "hi": ["hi", "hey"],
    "hello": ["hello", "helo", "heloo"],
    "who built you": ["who built you", "who made you", "your creator", "made you"]
}

_NORMALIZE_RE = re.compile(r"[^a-z0-9\s]")

def normalize(text: str) -> str:
    return _NORMALIZE_RE.sub("", text.lower().strip())

def match_faq_or_smalltalk(user_text: str) -> Optional[str]:
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