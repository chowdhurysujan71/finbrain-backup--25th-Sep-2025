"""
Continuous Coaching Flow Engine
Manages multi-turn conversations after summary/insight to help users pick actions
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import hardening components
try:
    from utils.coaching_analytics import coaching_analytics
    from utils.coaching_optimization import coaching_cache, performance_monitor
    from utils.coaching_resilience import coaching_resilience
    from utils.coaching_safeguards import coaching_circuit_breaker, feature_flag_manager
    HARDENING_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Coaching hardening components not available: {e}")
    HARDENING_AVAILABLE = False

# Coaching configuration from environment
COACH_MAX_TURNS = int(os.getenv('COACH_MAX_TURNS', '3'))
COACH_SESSION_TTL_SEC = int(os.getenv('COACH_SESSION_TTL_SEC', '300'))  # 5 min
COACH_COOLDOWN_SEC = int(os.getenv('COACH_COOLDOWN_SEC', '900'))  # 15 min
COACH_PER_DAY_MAX = int(os.getenv('COACH_PER_DAY_MAX', '6'))

def can_start_coach(intent: str, last_outbound_intent: str | None, user_text: str, redis_ok: bool, caps_ok: bool) -> bool:
    """
    Guard function: determines if coaching can be started
    
    Args:
        intent: Current resolved intent (SUMMARY, LOG, CORRECTION, etc.)
        last_outbound_intent: Previous outbound message intent (if available)
        user_text: User's message text
        redis_ok: Whether Redis is available
        caps_ok: Whether user is within daily/cooldown caps
    
    Returns:
        True if coaching can be started, False otherwise
    """
    from utils.structured import log_structured_event
    
    # Rule 1: NEVER start coaching for protected intents
    if intent in ['SUMMARY', 'LOG', 'CORRECTION']:
        log_structured_event("COACH_SKIPPED_INTENT", {
            "intent": intent,
            "reason": intent.lower()
        })
        return False
    
    # Rule 2: Redis failure = no coaching
    if not redis_ok:
        log_structured_event("COACH_DISABLED_NO_REDIS", {})
        return False
    
    # Rule 3: Rate limits must pass
    if not caps_ok:
        log_structured_event("COACH_END", {"reason": "cooldown"})
        return False
    
    # Rule 4a: Explicit opt-in with "insight"
    normalized_text = user_text.lower().strip().rstrip('.,!?')
    if normalized_text == "insight":
        return True
    
    # Rule 4b: Follow-up after INSIGHT/SUMMARY with valid responses
    if last_outbound_intent in ['INSIGHT', 'SUMMARY']:
        normalized_text = user_text.lower().strip().rstrip('.,!?')
        valid_responses = ['transport', 'food', 'other', 'yes', 'ok']
        if normalized_text in valid_responses:
            return True
    
    return False

def can_continue(state: str, user_text: str) -> bool:
    """
    Guard function: determines if coaching session can continue
    
    Args:
        state: Current coaching session state
        user_text: User's message text
    
    Returns:
        True if session can continue, False to end gracefully
    """
    from utils.structured import log_structured_event
    
    # Only continue if in valid continuation states
    if state not in ['await_focus', 'await_commit']:
        log_structured_event("COACH_END", {"reason": "mismatch"})
        return False
    
    # Check if user message matches expected continuation
    normalized_text = user_text.lower().strip()
    
    if state == 'await_focus':
        # Expecting topic selection or valid focus response
        valid_focus = ['transport', 'food', 'shopping', 'bills', 'other', 'yes', 'ok', 'sure']
        if any(term in normalized_text for term in valid_focus):
            return True
    
    elif state == 'await_commit':
        # Expecting commitment response
        valid_commit = ['yes', 'ok', 'sure', 'agree', 'will do', 'commit']
        if any(term in normalized_text for term in valid_commit):
            return True
    
    # If no match, end gracefully
    log_structured_event("COACH_END", {"reason": "user_optout"})
    return False

def get_last_outbound_intent(psid_hash: str) -> str | None:
    """
    Accessor for last outbound intent (if available in session/memory)
    
    Args:
        psid_hash: User's PSID hash
    
    Returns:
        Last outbound intent or None if not available
    """
    try:
        from utils.session import get_coaching_session
        session = get_coaching_session(psid_hash)
        return session.get('last_outbound_intent') if session else None
    except Exception:
        return None

def check_redis_health() -> bool:
    """
    Check if Redis is available and healthy
    
    Returns:
        True if Redis is healthy, False otherwise
    """
    try:
        from utils.session import session_manager
        if hasattr(session_manager, 'redis_client') and session_manager.redis_client:
            session_manager.redis_client.ping()
            return True
        return False
    except Exception:
        return False

def maybe_continue(psid_hash: str, intent: str, parsed_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    HARDENED coaching flow entry point - NEVER overrides normal replies
    Only triggers coaching when explicitly appropriate per safety rules
    
    Args:
        psid_hash: User's PSID hash
        intent: Resolved intent (SUMMARY, INSIGHT, LOG, etc.)
        parsed_data: Intent data (amounts, categories, etc.)
        
    Returns:
        Optional coaching reply payload or None to continue normal flow
    """
    start_time = time.time()
    
    try:
        # CRITICAL: Intent-first short-circuit - NEVER override protected intents
        if intent.upper() in ['SUMMARY', 'LOG', 'CORRECTION']:
            from utils.structured import log_structured_event
            log_structured_event("COACH_SKIPPED_INTENT", {
                "intent": intent.upper(),
                "reason": intent.lower()
            })
            return None
        
        # Check feature flags first
        if HARDENING_AVAILABLE and not feature_flag_manager.is_enabled('coaching_enabled', psid_hash):
            logger.debug(f"[COACH] Feature flag disabled for {psid_hash[:8]}...")
            return None
        
        # Use circuit breaker for resilience
        if HARDENING_AVAILABLE:
            return coaching_circuit_breaker.call(_maybe_continue_internal, psid_hash, intent, parsed_data, start_time)
        else:
            return _maybe_continue_internal(psid_hash, intent, parsed_data, start_time)
            
    except Exception as e:
        # Track error and fail safely
        if HARDENING_AVAILABLE:
            coaching_analytics.track_error('maybe_continue_error', str(e), psid_hash)
        logger.error(f"[COACH][ERROR] maybe_continue failed: {e}")
        return None

def _maybe_continue_internal(psid_hash: str, intent: str, parsed_data: dict[str, Any], start_time: float) -> dict[str, Any] | None:
    """Internal implementation with hardening and safety guards"""
    try:
        from utils.session import get_coaching_session, get_daily_coaching_count
        from utils.structured import log_structured_event
        
        # Check Redis health first
        redis_ok = check_redis_health()
        if not redis_ok:
            log_structured_event("COACH_DISABLED_NO_REDIS", {})
            return None
        
        # Check rate limits
        daily_count = get_daily_coaching_count(psid_hash)
        caps_ok = daily_count < COACH_PER_DAY_MAX
        
        # Get current session
        session = get_coaching_session(psid_hash) or {}
        state = session.get('state', 'idle')
        turns = session.get('turns', 0)
        
        # Check cooldown
        if state == 'cooldown':
            cooldown_until = session.get('cooldown_until', 0)
            if time.time() < cooldown_until:
                caps_ok = False
        
        # Check turn limits
        if turns >= COACH_MAX_TURNS:
            log_structured_event("COACH_END", {"reason": "turn_limit"})
            return None
        
        # Get last outbound intent for context
        last_outbound_intent = get_last_outbound_intent(psid_hash)
        
        # Use safety guards to determine if coaching can start
        user_text = parsed_data.get('original_text', '')
        if not can_start_coach(intent.upper(), last_outbound_intent, user_text, redis_ok, caps_ok):
            return None
        
        # Log coaching banner
        topic = session.get('topic', '-')
        logger.info(f"[COACH] state={state} turns={turns}/{COACH_MAX_TURNS} redis_ok={redis_ok} caps_ok={caps_ok} topic={topic} psid={psid_hash[:8]}...")
        
        # Only start coaching for explicit opt-in (user typed "insight")
        if state == 'idle' and user_text.lower().strip() == 'insight':
            log_structured_event("COACH_START", {"topic_suggestions": ["transport", "food", "other"]})
            return _start_coaching_flow(psid_hash, intent, parsed_data)
        
        return None
        
    except Exception as e:
        from utils.structured import log_structured_event
        log_structured_event("COACH_END", {"reason": "error"})
        logger.error(f"[COACH][ERROR] maybe_continue failed: {e}")
        return None

def handle_coaching_response(psid_hash: str, user_message: str) -> dict[str, Any] | None:
    """
    Handle user response in active coaching session
    
    Args:
        psid_hash: User's PSID hash
        user_message: User's message text
        
    Returns:
        Coaching reply payload or None if session not active
    """
    try:
        from utils.session import delete_coaching_session, get_coaching_session
        
        session = get_coaching_session(psid_hash)
        if not session or session.get('state') == 'idle':
            return None
        
        state = session.get('state')
        turns = session.get('turns', 0)
        last_question = session.get('last_question')
        
        # Check turn limit
        if turns >= COACH_MAX_TURNS:
            _end_coaching_session(psid_hash, 'turn_limit')
            return _create_coaching_reply("I'll let you get back to tracking. Type 'summary' anytime! 👍")
        
        # Use safety guard to determine if session can continue
        if not can_continue(state, user_message):
            # Guard determined session should end gracefully  
            _end_coaching_session(psid_hash, 'user_optout')
            return None
        
        user_text = user_message.lower().strip()
        
        # Handle state transitions
        if state == 'await_focus':
            return _handle_focus_response(psid_hash, user_text, session)
        elif state == 'await_commit':
            return _handle_commit_response(psid_hash, user_text, session)
        else:
            # Unknown state - reset
            delete_coaching_session(psid_hash)
            return None
            
    except Exception as e:
        logger.error(f"[COACH][ERROR] handle_coaching_response failed: {e}")
        return None

def _start_coaching_flow(psid_hash: str, intent: str, parsed_data: dict[str, Any]) -> dict[str, Any] | None:
    """Start new coaching flow from summary/insight"""
    from templates.replies_ai import coach_focus
    from utils.session import increment_daily_coaching_count, set_coaching_session
    from utils.structured import log_structured_event
    
    # Extract top category from data
    top_category = _extract_top_category(parsed_data)
    topic_suggestions = _get_topic_suggestions(top_category)
    
    # Increment daily counter
    increment_daily_coaching_count(psid_hash)
    
    # Create session
    session = {
        'state': 'await_focus',
        'last_question': 'focus',
        'topic': None,
        'suggestion': None,
        'turns': 1,
        'started_at': time.time()
    }
    set_coaching_session(psid_hash, session, COACH_SESSION_TTL_SEC)
    
    # Log telemetry
    log_structured_event("COACH_START", {"topic": top_category})
    log_structured_event("COACH_Q1_SENT", {"suggestions": topic_suggestions})
    
    # Generate focus question
    return coach_focus(topic_suggestions)

def _handle_focus_response(psid_hash: str, user_text: str, session: dict[str, Any]) -> dict[str, Any] | None:
    """Handle user's topic selection"""
    from templates.replies_ai import coach_commit
    from utils.session import set_coaching_session
    from utils.structured import log_structured_event
    
    # Parse topic selection
    topic = _parse_topic_selection(user_text)
    
    if user_text in {'skip', 'not now', 'later'}:
        _end_coaching_session(psid_hash, 'user_skip')
        return _create_coaching_reply("No worries! I'm here when you're ready. Type 'summary' anytime.")
    
    if not topic:
        # Re-ask once
        if session.get('turns', 0) < COACH_MAX_TURNS:
            session['turns'] = session.get('turns', 0) + 1
            set_coaching_session(psid_hash, session, COACH_SESSION_TTL_SEC)
            return _create_coaching_reply("Which area interests you most - transport, food, or something else?")
        else:
            _end_coaching_session(psid_hash, 'turn_limit')
            return _create_coaching_reply("I'll let you think about it. Type 'insight' when ready! ✨")
    
    # Generate action options for the topic
    action_options = _get_action_options(topic)
    
    # Update session
    session.update({
        'state': 'await_commit',
        'last_question': 'commit',
        'topic': topic,
        'turns': session.get('turns', 0) + 1
    })
    set_coaching_session(psid_hash, session, COACH_SESSION_TTL_SEC)
    
    log_structured_event("COACH_Q2_SENT", {"topic": topic, "options": action_options})
    
    return coach_commit(topic, action_options)

def _handle_commit_response(psid_hash: str, user_text: str, session: dict[str, Any]) -> dict[str, Any] | None:
    """Handle user's action commitment"""
    from templates.replies_ai import coach_done
    from utils.structured import log_structured_event
    
    if user_text in {'skip', 'not now', 'something else'}:
        _end_coaching_session(psid_hash, 'user_skip')
        return _create_coaching_reply("That's totally fine! Small steps when you're ready. 🌟")
    
    # Parse action selection
    action = _parse_action_selection(user_text, session.get('topic'))
    
    if not action:
        # Re-ask once
        if session.get('turns', 0) < COACH_MAX_TURNS:
            session['turns'] = session.get('turns', 0) + 1
            from utils.session import set_coaching_session
            set_coaching_session(psid_hash, session, COACH_SESSION_TTL_SEC)
            return _create_coaching_reply("Which option sounds doable for you this week?")
        else:
            _end_coaching_session(psid_hash, 'turn_limit')
            return _create_coaching_reply("Take your time deciding. I'm here when you need me! 👋")
    
    # Complete coaching session
    log_structured_event("COACH_ACTION_SELECTED", {"action": action, "topic": session.get('topic')})
    _end_coaching_session(psid_hash, 'completed')
    
    return coach_done(action)

def _end_coaching_session(psid_hash: str, reason: str):
    """End coaching session and set cooldown"""
    from utils.session import set_coaching_session
    from utils.structured import log_structured_event
    
    if reason == 'completed':
        # Set cooldown
        cooldown_session = {
            'state': 'cooldown',
            'cooldown_until': time.time() + COACH_COOLDOWN_SEC,
            'turns': 0
        }
        set_coaching_session(psid_hash, cooldown_session, COACH_COOLDOWN_SEC)
    else:
        # Just delete session
        from utils.session import delete_coaching_session
        delete_coaching_session(psid_hash)
    
    log_structured_event("COACH_END", {"reason": reason})

def _extract_top_category(parsed_data: dict[str, Any]) -> str:
    """Extract the top spending category from summary/insight data"""
    # This would extract from actual parsed summary data
    # For now, return a common category
    categories = parsed_data.get('categories', [])
    if categories:
        from utils.categories import normalize_category
        return categories[0] if isinstance(categories[0], str) else normalize_category(categories[0].get('category'))
    return 'transport'

def _get_topic_suggestions(top_category: str) -> list[str]:
    """Get topic suggestions based on top category"""
    suggestions = ['transport', 'food', 'other']
    
    # Put the top category first
    if top_category in suggestions:
        suggestions.remove(top_category)
        suggestions.insert(0, top_category)
    
    return suggestions

def _parse_topic_selection(user_text: str) -> str | None:
    """Parse user's topic selection from text"""
    text = user_text.lower()
    
    if any(word in text for word in ['transport', 'uber', 'taxi', 'ride', 'travel']):
        return 'transport'
    elif any(word in text for word in ['food', 'meal', 'eat', 'restaurant', 'lunch', 'dinner']):
        return 'food'
    elif any(word in text for word in ['shop', 'buy', 'purchase', 'clothes']):
        return 'shopping'
    elif any(word in text for word in ['other', 'different', 'else']):
        return 'other'
    
    return None

def _get_action_options(topic: str) -> list[str]:
    """Get actionable options for a topic"""
    options = {
        'transport': ['batch trips', 'off-peak'],
        'food': ['meal prep', 'cook more'],
        'shopping': ['set budget', 'wait 24h'],
        'other': ['track closer', 'set limit']
    }
    return options.get(topic, ['track closer', 'set goal'])

def _parse_action_selection(user_text: str, topic: str | None) -> str | None:
    """Parse user's action selection"""
    text = user_text.lower()
    
    if topic and topic == 'transport':
        if any(word in text for word in ['batch', 'group', 'combine']):
            return 'batch trips'
        elif any(word in text for word in ['off-peak', 'timing', 'different time']):
            return 'off-peak'
    elif topic and topic == 'food':
        if any(word in text for word in ['prep', 'plan', 'cook']):
            return 'meal prep'
        elif any(word in text for word in ['cook', 'home', 'make']):
            return 'cook more'
    
    # Default action parsing
    if any(word in text for word in ['first', '1', 'batch', 'group']):
        return _get_action_options(topic)[0]
    elif any(word in text for word in ['second', '2', 'off', 'time']):
        return _get_action_options(topic)[1] if len(_get_action_options(topic)) > 1 else _get_action_options(topic)[0]
    
    return None

def _create_coaching_reply(text: str, quick_replies: list[str] | None = None) -> dict[str, Any]:
    """Create coaching reply payload"""
    reply = {
        'text': text,
        'intent': 'coaching',
        'category': None,
        'amount': None
    }
    
    if quick_replies:
        reply['quick_replies'] = [{'title': qr, 'payload': f'COACH_{qr.upper().replace(" ", "_")}'} for qr in quick_replies]
    
    return reply