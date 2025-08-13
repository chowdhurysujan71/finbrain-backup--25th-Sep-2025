"""
Runtime flags for feature toggling
Allows real-time AI enable/disable without restart
"""
from config import AI_ENABLED as AI_DEFAULT

class Flags:
    """Runtime feature flags"""
    ai_enabled = AI_DEFAULT

FLAGS = Flags()

def is_ai_enabled():
    """Check if AI is currently enabled"""
    return FLAGS.ai_enabled

def toggle_ai(enabled: bool):
    """Toggle AI on/off at runtime"""
    FLAGS.ai_enabled = enabled
    return FLAGS.ai_enabled