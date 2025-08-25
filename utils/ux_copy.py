# utils/ux_copy.py
"""
Centralized UX copy for finbrain guardrails and messaging
All user-facing text in one place for consistency and easy updates
"""

SLOW_DOWN = "⚠️ You're sending messages very fast—please slow down."
DAILY_LIMIT = "⏳ You've reached today's limit of 30 messages. Please come back tomorrow."
REPEAT_HINT = "Got that—anything new you'd like me to do now: log, summary, or insight?"
PII_WARNING = "🔒 For your security, please don't share sensitive information here."
BUSY = "⏳ finbrain is a bit busy right now. Please try again in a few minutes."
FALLBACK = ("🧭 I can help you log expenses, show summaries, or share insights. "
            "Try: 'coffee 120' or 'summary this week'. For details visit www.finbrain.app")

# Budget comparison enhancements (additive only)
BUDGET_WEEK_COMPARISON = "📊 vs last week: {change_symbol}{pct}%"
BUDGET_MONTH_COMPARISON = "📈 vs last month: {change_symbol}{pct}%"
BUDGET_TOP_CHANGE = " • Biggest change: {category}"
BUDGET_NO_DATA = "📭 Need more history for comparison—keep logging!"