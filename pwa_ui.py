"""
PWA UI Blueprint - Modern, installable expense tracking interface
"""
import logging
import time

from flask import Blueprint, current_app, g, jsonify, render_template, request, Response, redirect
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from models import User

try:
    from utils.rate_limiting import limiter
except ImportError:
    # Create a dummy limiter that doesn't do anything
    class DummyLimiter:
        def limit(self, limit_string):
            def decorator(func):
                return func  # Just return the function unchanged
            return decorator
    limiter = DummyLimiter()

logger = logging.getLogger(__name__)

pwa_ui = Blueprint('pwa_ui', __name__)

def require_auth():
    """Helper function to ensure user is authenticated via session with DB retry logic"""
    from flask import abort, session
    from models import User
    
    # Check if user is logged in via session
    user_id_hash = session.get('user_id')
    if not user_id_hash:
        abort(401)
        
    # Get user from database
    user = User.query.filter_by(user_id_hash=user_id_hash).first()
    if not user:
        session.clear()
        abort(401)
        
    return user

def require_auth_or_redirect() -> Union['User', Response]:
    """Helper function to redirect to login if user is not authenticated"""
    import time

    from flask import request, session
    from sqlalchemy.exc import DisconnectionError, OperationalError

    from db_base import db
    from models import User
    
    # Check if user is logged in via session
    user_id_hash = session.get('user_id')
    if not user_id_hash:
        # Redirect to login with returnTo parameter
        return redirect(f"/login?returnTo={request.path}")
    
    # Find user in database with retry logic for SSL connection issues
    max_retries = 3
    retry_delay = 0.1  # 100ms initial delay
    
    for attempt in range(max_retries):
        try:
            user = User.query.filter_by(user_id_hash=user_id_hash).first()
            if not user:
                # Session is invalid, clear it and redirect
                session.clear()
                return redirect(f"/login?returnTo={request.path}")
            
            return user
            
        except (OperationalError, DisconnectionError) as e:
            # Handle SSL connection errors and other database connectivity issues
            if attempt < max_retries - 1:
                # Log the retry attempt
                logger.warning(f"Database connection error in require_auth_or_redirect (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}...")
                
                # Dispose of current connection pool to force fresh connections
                try:
                    db.engine.dispose()
                except Exception as dispose_error:
                    logger.debug(f"Engine dispose error: {dispose_error}")
                
                # Exponential backoff with jitter
                delay = retry_delay * (2 ** attempt) + (time.time() % 0.1)
                time.sleep(delay)
                continue
            else:
                # Last attempt failed, log error and abort
                logger.error(f"Database connection failed after {max_retries} attempts in require_auth_or_redirect: {str(e)}")
                # Return 503 Service Unavailable instead of 500 for DB connectivity issues
                from flask import abort
                abort(503)
        
        except Exception as e:
            # Handle non-connection related database errors
            logger.error(f"Non-connection database error in require_auth_or_redirect: {str(e)}")
            from flask import abort
            abort(500)
    
    # Fallback return (should never reach here due to abort calls above)
    return redirect("/login")
    

# Safe JSON helper function
def _json():
    """Safely get JSON from request, return empty dict if parsing fails"""
    try:
        return request.get_json(force=False, silent=True) or {}
    except Exception:
        return {}

def get_user_id():
    """Get user ID hash from session only - SECURITY: Never read from headers"""
    from flask import session
    
    # ONLY check session for authenticated users
    if 'user_id' in session:
        return session['user_id']
    
    # Return None for unauthenticated users - no header fallback
    return None

def _safe_get_user_id():
    """Safely get user ID from Flask g context with error handling"""
    try:
        return getattr(g, 'user_id', 'anonymous')
    except RuntimeError:
        # g is not available outside of request context
        return 'anonymous'

# Request logging for chat debugging
@pwa_ui.before_app_request
def _debug_chat_requests():
    """Log chat requests for frontend-backend correlation"""
    if request.path == '/ai-chat' and request.method == 'POST':
        current_app.logger.info('ai-chat start uid=%s ctype=%s', 
                              getattr(g, 'user_id', 'anonymous'),
                              request.headers.get('Content-Type'))

def handle_with_fallback_ai(user_id_hash, user_message, conversational_ai=None):
    """Handle chat message using fallback AI when main router is unavailable"""
    try:
        logger.info(f"Fallback handler processing: '{user_message[:30]}...'")
        
        # Check if message is about expenses
        if any(word in user_message.lower() for word in ['spent', 'taka', '৳', 'cost', 'paid', 'bought', 'expense']):
            logger.info("Detected expense-related message, attempting to parse")
            # Try to parse expense from message
            try:
                # Simple regex-based parsing for basic expenses
                import re
                
                # Look for amount patterns
                amount_match = re.search(r'(\d+(?:\.\d{1,2})?)', user_message)
                if amount_match:
                    amount = float(amount_match.group(1))
                    
                    # Simple category detection
                    category = 'uncategorized'
                    if any(word in user_message.lower() for word in ['food', 'lunch', 'dinner', 'eat', 'restaurant']):
                        category = 'food'
                    elif any(word in user_message.lower() for word in ['transport', 'bus', 'taxi', 'uber', 'rickshaw']):
                        category = 'transport'
                    elif any(word in user_message.lower() for word in ['shop', 'buy', 'purchase', 'store']):
                        category = 'shopping'
                    
                    # Save expense using CANONICAL SINGLE WRITER (spec compliance)
                    import backend_assistant as ba
                    
                    logger.info(f"Attempting to save expense: {amount} taka for {category}")
                    result = ba.add_expense(
                        user_id=user_id_hash,
                        amount_minor=int(amount * 100),  # Convert to minor units
                        currency='BDT',
                        category=category,
                        description=user_message,
                        source='chat',  # Web chat uses 'chat' source per spec
                        message_id=f"pwa_chat_{int(time.time())}"
                    )
                    logger.info(f"Expense saved successfully: {result}")
                    return f"✅ Logged expense: ৳{amount} for {category}"
                else:
                    logger.info("No amount found in expense message")
                    return "I understand you want to log an expense. Please include the amount, like: 'I spent 100 taka on food'"
                    
            except Exception as e:
                logger.warning(f"Simple expense parsing failed: {e}")
                return "I understand you want to log an expense. Please use the format: 'I spent 100 taka on food'"
        else:
            logger.info("Processing general conversation message")
            # Skip potentially hanging conversational AI, use simple responses
            responses = [
                "I'm your AI expense assistant! Try saying things like 'I spent 200 taka on lunch'",
                "Hi! I can help you track expenses. Just tell me what you spent money on!",
                "Hello! I'm here to help with your expenses. Try: 'I bought groceries for 150 taka'",
                "I can log your expenses! Try telling me: 'I spent 50 taka on transport'"
            ]
            # Use hash of user message to pick consistent response
            response_index = hash(user_message) % len(responses)
            return responses[response_index]
            
    except Exception as e:
        logger.error(f"Fallback AI handler error: {e}")
        return "I'm here to help with your expenses! Try telling me about something you spent money on."

@pwa_ui.route('/chat')
def chat():
    """
    Expense input + recent entries list (HTMX partial hydrate)
    AUTHENTICATION REQUIRED
    """
    user = require_auth_or_redirect()  # Require authentication or redirect to login
    
    # If it's a redirect response, return it directly
    if isinstance(user, Response):
        return user
        
    if not user:  # In case it returns None instead of redirecting
        from flask import redirect
        return redirect("/login?returnTo=/chat")
    
    logger.info(f"PWA chat route accessed by user: {user.user_id_hash}")
    
    return render_template('chat.html', user_id=user.user_id_hash)

@pwa_ui.route('/report')
def report():
    """
    Money Story summary cards + placeholder charts
    AUTHENTICATION REQUIRED
    """
    user = require_auth_or_redirect()  # Require authentication or redirect to login
    
    # If it's a redirect response, return it directly
    if isinstance(user, Response):
        return user
        
    if not user:  # In case it returns None instead of redirecting
        from flask import redirect
        return redirect("/login?returnTo=/report")
    
    logger.info(f"PWA report route accessed by user: {user.user_id_hash}")
    
    return render_template('report.html', user_id=user.user_id_hash)


@pwa_ui.route('/profile')
def profile():
    """
    Profile summary showing user info if available
    AUTHENTICATION REQUIRED
    Feature-flagged: FEATURE_PROFILE_V2 enables new Google/Stripe-grade profile UI
    """
    import os
    user = require_auth_or_redirect()  # Require authentication or redirect to login
    
    # If it's a redirect response, return it directly
    if isinstance(user, Response):
        return user
        
    if not user:  # In case it returns None instead of redirecting
        from flask import redirect
        return redirect("/login?returnTo=/profile")
    
    logger.info(f"PWA profile route accessed by user: {user.user_id_hash}")
    
    # Feature flag: Use profile v2 if enabled, otherwise fallback to current
    feature_flag_raw = os.environ.get('FEATURE_PROFILE_V2', '')
    feature_v2_enabled = str(feature_flag_raw).lower() in ('1', 'true', 'yes', 'on')
    
    logger.info(f"FEATURE_PROFILE_V2='{feature_flag_raw}' resolved={feature_v2_enabled}")
    
    if feature_v2_enabled:
        logger.info(f"Using profile v2 for user: {user.user_id_hash}")
        return render_template('profile_v2.html', user_id=user.user_id_hash)
    else:
        logger.info(f"Using profile v1 (fallback) for user: {user.user_id_hash}")
        return render_template('profile.html', user_id=user.user_id_hash)

@pwa_ui.route('/challenge')
def challenge():
    """
    3-day challenge progress UI with goal-setting functionality
    AUTHENTICATION REQUIRED
    """
    from flask import request
    
    user = require_auth_or_redirect()  # Require authentication or redirect to login
    
    # If it's a redirect response, return it directly
    if isinstance(user, Response):
        return user
        
    if not user:  # In case it returns None instead of redirecting
        from flask import redirect
        return redirect("/login?returnTo=/challenge")
    
    # Get action parameter (e.g., ?action=set_goal from banner)
    action = request.args.get('action')
    
    # Fetch existing goals for the user
    active_goals = []
    goal_progress = None
    
    try:
        # Import Goal model and database to fetch user goals
        from models import Goal, Expense
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from db_base import db
        
        # Get active goals
        active_goals = Goal.get_active_for_user(user.user_id_hash, 'daily_spend_under')
        
        # If user has an active daily spending goal, get weekly progress
        if active_goals:
            goal = active_goals[0]
            
            # Calculate week range (Monday to Sunday)
            from utils.timezone import get_current_time
            now = get_current_time()
            days_since_monday = now.weekday()
            monday = (now - timedelta(days=days_since_monday)).date()
            
            # Get daily spending for current week
            week_expenses = db.session.query(
                func.DATE(Expense.date).label('date'),
                func.sum(Expense.amount).label('spent')
            ).filter(
                Expense.user_id_hash == user.user_id_hash,
                Expense.date >= monday,
                Expense.date <= now.date(),
                Expense.is_deleted.is_(False)  # Exclude soft-deleted expenses
            ).group_by(func.DATE(Expense.date)).all()
            
            # Build daily progress
            days = []
            ok_days = 0
            over_days = 0
            
            for i in range(7):  # Monday to Sunday
                day_date = monday + timedelta(days=i)
                day_spent = 0
                
                # Find spending for this day
                for expense_day in week_expenses:
                    if expense_day.date == day_date:
                        day_spent = float(expense_day.spent)
                        break
                
                is_ok = day_spent <= float(goal.amount)
                if day_spent > 0:  # Only count days with spending
                    if is_ok:
                        ok_days += 1
                    else:
                        over_days += 1
                
                days.append({
                    "date": day_date.isoformat(),
                    "day_name": day_date.strftime("%A"),
                    "spent": day_spent,
                    "limit": float(goal.amount),
                    "ok": is_ok,
                    "is_today": day_date == now.date()
                })
            
            goal_progress = {
                "goal": goal.to_dict(),
                "days": days,
                "summary": {
                    "ok_days": ok_days,
                    "over_days": over_days,
                    "total_days_with_spending": ok_days + over_days
                }
            }
            
    except Exception as e:
        logger.error(f"Error fetching goal data for challenge page: {e}")
        active_goals = []
        goal_progress = None
    
    logger.info(f"PWA challenge route accessed by user: {user.user_id_hash}, action: {action}, goals: {len(active_goals)}")
    
    return render_template('challenge.html', 
                         user_id=user.user_id_hash,
                         action=action,
                         active_goals=active_goals,
                         goal_progress=goal_progress,
                         show_goal_wizard=action == 'set_goal' or len(active_goals) == 0)

@pwa_ui.route('/admin/chat')
def admin_chat():
    """
    Admin chat interface
    AUTHENTICATION REQUIRED - Redirects to login if not authenticated
    """
    from flask import Response, redirect
    
    user = require_auth_or_redirect()
    if isinstance(user, Response):
        # This is a redirect response
        return user
    
    logger.info(f"Admin chat route accessed by user: {user.user_id_hash}")
    
    # For now, redirect to regular chat - later can be enhanced with admin features
    return redirect('/chat')

@pwa_ui.route('/login')
def login():
    """
    Login page for user registration system with returnTo support
    """
    from flask import request

    from auth_helpers import validate_return_to_url
    
    # Get and validate returnTo parameter
    return_to = request.args.get('returnTo', '')
    if return_to and not validate_return_to_url(return_to):
        # Invalid returnTo URL, ignore it for security
        return_to = ''
    
    return render_template('login.html', return_to=return_to)

@pwa_ui.route('/register')
def register():
    """
    Registration page for new users
    """
    return render_template('register.html')

@pwa_ui.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def auth_login():
    """
    Process user login with CAPTCHA protection and returnTo redirect support
    """
    from flask import jsonify, redirect, request, session
    from werkzeug.security import check_password_hash

    from auth_helpers import validate_return_to_url
    from models import User
    from utils.captcha import verify_nonce_captcha
    
    try:
        data = request.get_json(silent=True) or {}
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        captcha_answer = data.get('captcha_answer', '').strip()
        captcha_nonce = data.get('captcha_nonce', '').strip()
        return_to = data.get('returnTo', '').strip()
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
        if not captcha_answer or not captcha_nonce:
            return jsonify({"error": "CAPTCHA answer and nonce required"}), 400
        
        # Verify CAPTCHA before processing authentication
        captcha_valid, captcha_error = verify_nonce_captcha(captcha_nonce, captcha_answer)
        if not captcha_valid:
            logger.warning(f"Failed CAPTCHA attempt for login: {email} - {captcha_error}")
            return jsonify({"error": f"CAPTCHA failed: {captcha_error}"}), 400
        
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Create session using Flask's built-in session system
        session.permanent = True  # Make session permanent for 30-day lifetime
        session['user_id'] = user.user_id_hash
        session['email'] = email
        session['is_registered'] = True
        
        logger.info(f"User {email} logged in successfully")
        
        # UX IMPROVEMENT: Detect AJAX vs form submission for proper response handling
        is_ajax_request = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '') or
            request.headers.get('Content-Type', '').startswith('application/json')
        )
        
        # Handle returnTo redirect for subdomain authentication
        if return_to and validate_return_to_url(return_to):
            logger.info(f"Redirecting authenticated user to: {return_to}")
            
            if is_ajax_request:
                # AJAX request: return JSON with redirect instruction
                return jsonify({
                    "success": True, 
                    "message": "Login successful",
                    "redirect": return_to,
                    "data": {"user_id": user.user_id_hash}
                }), 200
            else:
                # Non-AJAX request: server-side redirect for robustness
                logger.info(f"Server-side redirect for non-AJAX login to: {return_to}")
                return redirect(return_to, code=302)
        
        # Default response when no returnTo specified
        if is_ajax_request:
            # AJAX request: return JSON response
            return jsonify({
                "success": True, 
                "message": "Login successful",
                "data": {"user_id": user.user_id_hash}
            }), 200
        else:
            # Non-AJAX request: redirect to default authenticated page
            default_redirect = "/chat"  # Default page for authenticated users
            logger.info(f"Server-side redirect for non-AJAX login to default: {default_redirect}")
            return redirect(default_redirect, code=302)
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"error": "Login failed. Please try again."}), 500

@pwa_ui.route('/api/auth/me', methods=['GET'])
def auth_me():
    """
    Check current user session and return user info or 401
    Cheap and reliable endpoint for frontend auth state checking
    """
    from flask import jsonify, session

    from models import User
    
    try:
        # Check if user is logged in via session
        user_id_hash = session.get('user_id')
        if not user_id_hash:
            return jsonify({"error": "Not authenticated"}), 401
        
        # Find user in database
        user = User.query.filter_by(user_id_hash=user_id_hash).first()
        if not user:
            # Session is invalid, clear it
            session.clear()
            return jsonify({"error": "Invalid session"}), 401
        
        # Return user info with consistent user_id_hash
        return jsonify({
            "ok": True,
            "user_id": user.user_id_hash,  # Use hash for consistency
            "email": user.email,
            "name": user.name or "User",
            "id": user.id  # Include numeric ID if needed
        }), 200
        
    except Exception as e:
        logger.error(f"Auth check error: {e}")
        return jsonify({"error": "Auth check failed"}), 500

@pwa_ui.route('/api/auth/register', methods=['POST'])
@limiter.limit("3 per minute")
def auth_register():
    """
    Process user registration with CAPTCHA protection and comprehensive validation
    """
    import time
    import uuid

    from flask import jsonify, request, session
    from werkzeug.security import generate_password_hash

    from db_base import db
    from models import User
    from utils.captcha import verify_nonce_captcha
    from utils.identity import psid_hash
    
    try:
        data = request.get_json(silent=True) or {}
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        captcha_answer = data.get('captcha_answer', '').strip()
        captcha_nonce = data.get('captcha_nonce', '').strip()
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
        if not captcha_answer or not captcha_nonce:
            return jsonify({"error": "CAPTCHA answer and nonce required"}), 400
        
        # Verify CAPTCHA before processing registration
        captcha_valid, captcha_error = verify_nonce_captcha(captcha_nonce, captcha_answer)
        if not captcha_valid:
            logger.warning(f"Failed CAPTCHA attempt for registration: {email} - {captcha_error}")
            return jsonify({"error": f"CAPTCHA failed: {captcha_error}"}), 400
        
        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "Account already exists"}), 409
        
        # Generate user hash
        user_id = f"pwa_reg_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        user_hash = psid_hash(user_id)
        
        # Create user
        user = User()
        user.user_id_hash = user_hash
        user.email = email
        user.password_hash = generate_password_hash(password)
        user.name = name
        user.platform = 'pwa'
        user.first_name = name.split()[0] if name else ''
        user.total_expenses = 0
        user.expense_count = 0
        user.daily_message_count = 0
        user.hourly_message_count = 0
        user.interaction_count = 0
        user.onboarding_step = 0
        user.consecutive_days = 0
        user.reports_requested = 0
        
        db.session.add(user)
        db.session.commit()
        
        # Create permanent session (30-day lifetime)
        session.permanent = True
        session['user_id'] = user_hash
        session['email'] = email
        session['is_registered'] = True
        
        return jsonify({
            "success": True,
            "message": "Registration successful", 
            "data": {"user_id": user_hash}
        }), 200
        
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Registration failed. Please try again."}), 500

@pwa_ui.route('/api/auth/captcha', methods=['GET'])
@limiter.limit("10 per minute")
def generate_captcha():
    """
    Generate CAPTCHA for authentication endpoints
    Returns a math question and nonce for the user to solve
    """
    from flask import jsonify

    from utils.captcha import generate_nonce_captcha
    
    try:
        captcha_data = generate_nonce_captcha()
        return jsonify({
            "success": True,
            "question": captcha_data['question'],
            "nonce": captcha_data['nonce']
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating CAPTCHA: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to generate CAPTCHA",
            "question": "What is 2 + 2?",  # Fallback
            "nonce": "fallback_nonce"
        }), 500

@pwa_ui.route('/auth/logout', methods=['POST'])
def auth_logout():
    """
    Process user logout with cross-subdomain cookie clearing
    """
    from flask import jsonify, make_response, session
    
    # Clear the session
    session.clear()
    
    # Create response
    response = make_response(jsonify({
        'success': True,
        'message': 'Logged out successfully',
        'redirect': '/login'
    }))
    
    # Clear the custom session cookie for all finbrain.app subdomains
    # This ensures the cookie is cleared across all subdomains
    response.set_cookie(
        'fbn.sid',  # Our custom session cookie name
        '',  # Empty value
        domain='.finbrain.app',  # Clear for all subdomains
        expires=0,  # Immediate expiration
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    
    # Also clear the default Flask session cookie as a fallback
    response.set_cookie(
        'session',  # Default Flask session cookie name
        '',  # Empty value
        domain='.finbrain.app',  # Clear for all subdomains
        expires=0,  # Immediate expiration
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    
    logger.info("User logged out successfully, cookies cleared for all subdomains")
    return response

@pwa_ui.route('/api/auth/generate-guest-token', methods=['POST'])
@limiter.limit("20 per minute")
def generate_guest_token():
    """
    Generate a secure link token for a guest ID
    Called by PWA when creating guest sessions
    """
    from flask import jsonify, request

    from utils.guest_tokens import generate_guest_token as create_token
    
    try:
        data = request.get_json(silent=True) or {}
        guest_id = data.get('guest_id', '').strip()
        
        if not guest_id:
            return jsonify({"error": "Guest ID is required"}), 400
        
        # Validate guest ID format (prevent abuse)
        if not guest_id.startswith('pwa_user_') or len(guest_id) > 100:
            return jsonify({"error": "Invalid guest ID format"}), 400
        
        # Generate secure token
        token = create_token(guest_id, validity_hours=720)  # 30 days
        
        logger.info(f"Generated secure token for guest {guest_id[:12]}***")
        
        return jsonify({
            "ok": True,
            "guest_id": guest_id,
            "link_token": token
        }), 200
        
    except Exception as e:
        logger.error(f"Token generation error: {e}")
        return jsonify({"error": "Token generation failed"}), 500

@pwa_ui.route('/api/auth/link-guest', methods=['POST'])
@limiter.limit("10 per minute")
def link_guest_data():
    """
    Link guest expense data to authenticated user account (SECURE VERSION)
    Requires valid guest ID and cryptographic link token to prevent unauthorized access
    Transfers all guest expenses to the authenticated user's account
    """
    from flask import jsonify, request

    from db_base import db
    from models import Expense
    from utils.guest_tokens import (
        is_token_recently_used,
        mark_token_as_used,
        verify_guest_token,
    )
    from utils.identity import psid_hash
    
    try:
        # Ensure user is authenticated
        user = require_auth()
        
        # Get guest ID and link token from request
        data = request.get_json(silent=True) or {}
        guest_id = data.get('guest_id', '').strip()
        link_token = data.get('link_token', '').strip()
        
        # Validate required parameters
        if not guest_id:
            return jsonify({"error": "Guest ID is required"}), 400
        
        if not link_token:
            return jsonify({"error": "Link token is required for security"}), 400
        
        # Verify the guest token
        is_valid, token_data = verify_guest_token(link_token, guest_id)
        if not is_valid:
            error_msg = token_data.get('error', 'Unknown error') if token_data else 'Unknown error'
            logger.warning(f"Invalid guest token attempt from user {user.user_id_hash[:8]}*** for guest {guest_id[:8]}***: {error_msg}")
            return jsonify({
                "error": "Invalid or expired link token",
                "details": "Guest data merge requires valid authentication token"
            }), 401
        
        # Check for token reuse (basic replay protection)
        token_nonce = token_data.get('nonce', '') if token_data else ''
        if token_nonce and is_token_recently_used(guest_id, token_nonce):
            logger.warning(f"Token reuse attempt from user {user.user_id_hash[:8]}*** for guest {guest_id[:8]}***")
            return jsonify({"error": "Token has already been used"}), 401
        
        # Generate guest hash for database lookup
        guest_hash = psid_hash(guest_id)
        
        # Begin database transaction for safety
        try:
            # Check for expenses with both hashed and unhashed guest IDs for backward compatibility
            expenses_updated = 0
            
            # First try with hashed guest ID
            hashed_count = db.session.query(Expense).filter(
                Expense.user_id_hash == guest_hash
            ).update({
                'user_id_hash': user.user_id_hash,
                'user_id': user.user_id_hash,  # Also update legacy user_id field
                'platform': 'pwa'  # Ensure platform is consistent
            })
            expenses_updated += hashed_count
            
            # Then try with unhashed guest ID (for backward compatibility)
            unhashed_count = db.session.query(Expense).filter(
                Expense.user_id_hash == guest_id
            ).update({
                'user_id_hash': user.user_id_hash,
                'user_id': user.user_id_hash,  # Also update legacy user_id field
                'platform': 'pwa'  # Ensure platform is consistent
            })
            expenses_updated += unhashed_count
            
            # Mark token as used to prevent replay attacks (before committing)
            if token_nonce:
                mark_token_as_used(guest_id, token_nonce)
            
            # Commit the transaction
            db.session.commit()
            
            logger.info(f"SECURE Guest data merged: {expenses_updated} expenses transferred from guest {guest_id[:8]}*** to user {user.user_id_hash[:8]}*** with verified token")
            
            return jsonify({
                "ok": True,
                "expenses_merged": expenses_updated,
                "message": f"Successfully merged {expenses_updated} expenses",
                "security": "Token verified and invalidated"
            }), 200
            
        except Exception as db_error:
            # Rollback on database error
            db.session.rollback()
            logger.error(f"Database error during guest data merge: {db_error}")
            return jsonify({"error": "Failed to merge guest data"}), 500
            
    except Exception as e:
        logger.error(f"Error in link_guest_data: {e}")
        return jsonify({"error": "Failed to process guest data linking"}), 500

@pwa_ui.route('/api/profile', methods=['GET'])
def api_profile():
    """
    Profile data aggregator endpoint for Profile V2 UI
    Returns user stats, goals, insights, and recent activity
    AUTHENTICATION REQUIRED - Cache-Control: no-store for security
    """
    from flask import jsonify, session
    from datetime import datetime, timedelta
    from sqlalchemy import func, desc
    from models import User, Expense, Goal
    from db_base import db
    
    try:
        # Check authentication (same pattern as auth_me)
        user_id_hash = session.get('user_id')
        if not user_id_hash:
            return jsonify({"error": "Not authenticated"}), 401
        
        # Find user in database
        user = User.query.filter_by(user_id_hash=user_id_hash).first()
        if not user:
            session.clear()
            return jsonify({"error": "Invalid session"}), 401
        
        # Calculate current month date range
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        
        # --- USER INFO ---
        user_data = {
            "masked_id": f"usr_{user.user_id_hash[:8]}...{user.user_id_hash[-4:]}",
            "member_since": user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else "2024-10-01T00:00:00Z",
            "status": "active",
            "app_version": "v0.9.7"
        }
        
        # --- STATS (Current Month) ---
        # Total expenses this month
        month_expenses = Expense.query_active().filter(
            Expense.user_id_hash == user_id_hash,
            Expense.date >= month_start,
            Expense.date < next_month.date()
        ).all()
        
        expense_count = len(month_expenses)
        total_spent = sum(float(exp.amount) for exp in month_expenses)
        
        # Active days (days with expenses this month)
        active_days = len(set(exp.date for exp in month_expenses))
        
        # Categories used this month
        categories = set(exp.category for exp in month_expenses)
        category_count = len(categories)
        
        # Goal success rate (simplified calculation)
        goal_success_rate = 0.83  # Default fallback
        daily_budget = 500  # Default fallback
        
        try:
            # Get user's active daily spending goal
            active_goal = Goal.query.filter_by(
                user_id_hash=user_id_hash, 
                type='daily_spend_under', 
                status='active'
            ).first()
            
            if active_goal:
                daily_budget = float(active_goal.amount)
                
                # Calculate success rate for last 7 days
                week_start = (now - timedelta(days=7)).date()
                daily_spending = db.session.query(
                    func.DATE(Expense.date).label('date'),
                    func.sum(Expense.amount).label('spent')
                ).filter(
                    Expense.user_id_hash == user_id_hash,
                    Expense.date >= week_start,
                    Expense.date <= now.date(),
                    Expense.is_deleted.is_(False)
                ).group_by(func.DATE(Expense.date)).all()
                
                if daily_spending:
                    success_days = sum(1 for day in daily_spending if float(day.spent) <= daily_budget)
                    goal_success_rate = success_days / len(daily_spending)
        except Exception as goal_error:
            logger.warning(f"Goal calculation error: {goal_error}")
        
        stats_data = {
            "month": now.strftime("%Y-%m"),
            "expense_count": expense_count,
            "total_spent": total_spent,
            "active_days": active_days,
            "category_count": category_count,
            "goal_success_rate": goal_success_rate
        }
        
        # --- GOALS ---
        current_streak_days = 4  # Simplified for now
        ai_next_goal_suggestion = daily_budget + 50  # Simple suggestion
        
        goals_data = {
            "daily_budget": daily_budget,
            "current_streak_days": current_streak_days,
            "ai_next_goal_suggestion": ai_next_goal_suggestion
        }
        
        # --- INSIGHTS ---
        insights_data = {
            "top_tip": "You're tracking expenses consistently! Keep it up for better financial insights.",
            "trend": "up" if total_spent > 10000 else "down",
            "confidence": 0.78
        }
        
        # --- RECENT ACTIVITY ---
        recent_expenses = Expense.query_active().filter_by(
            user_id_hash=user_id_hash
        ).order_by(desc(Expense.created_at)).limit(5).all()
        
        recent_data = []
        for exp in recent_expenses:
            recent_data.append({
                "id": exp.id,
                "ts": exp.created_at.isoformat(),
                "category": exp.category,
                "amount": float(exp.amount),
                "note": exp.description or exp.category
            })
        
        # Return aggregated profile data
        response_data = {
            "user": user_data,
            "stats": stats_data,
            "goals": goals_data,
            "insights": insights_data,
            "recent": recent_data
        }
        
        # Set cache headers for security
        response = jsonify(response_data)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        
        logger.info(f"Profile data served for user: {user.user_id_hash[:8]}...")
        return response, 200
        
    except Exception as e:
        logger.error(f"Error in api_profile: {e}")
        return jsonify({"error": "Failed to load profile data"}), 500

@pwa_ui.route('/v1/meta/categories', methods=['GET'])
def meta_categories():
    """
    🎯 LOCK 3: Categories contract endpoint
    Returns canonical categories and synonym mappings for clients
    """
    from flask import jsonify
    
    return jsonify({
        "allowed": ["food", "transport", "bills", "shopping", "uncategorized"],
        "synonyms": {
            "other": "uncategorized",
            "misc": "uncategorized", 
            "miscellaneous": "uncategorized",
            "groceries": "food",
            "grocery": "food",
            "dinner": "food",
            "lunch": "food", 
            "breakfast": "food",
            "uber": "transport",
            "taxi": "transport",
            "bus": "transport",
            "utilities": "bills",
            "utility": "bills",
            "clothes": "shopping",
            "clothing": "shopping"
        }
    }), 200

@pwa_ui.route('/offline')
def offline():
    """
    Offline fallback page for PWA
    Minimal functionality when network unavailable
    """
    return render_template('offline.html')

# HTMX partial routes for dynamic content
@pwa_ui.route('/partials/entries')
def entries_partial():
    """
    Recent entries partial for HTMX - UI GUARDRAILS ENFORCED
    MUST use session-authenticated API endpoints only
    """
    from flask import session
    
    try:
        # SECURITY: Only session-authenticated users can see entries
        if 'user_id' not in session:
            logger.warning("Unauthorized access to /partials/entries - no session")
            return render_template('partials/entries.html', entries=[])
        
        # Call the backend function directly (bypass HTTP layer)
        from backend_assistant import get_recent_expenses
        from utils.identity import ensure_hashed
        
        # Get user hash for database lookup  
        user_id_hash = ensure_hashed(session['user_id'])
        
        # Call the backend function directly with proper parameters
        expenses_data = get_recent_expenses(user_id_hash, limit=10)
        
        # Convert backend response to template format
        entries = []
        for expense in expenses_data:
            entries.append({
                'id': expense.get('id', 0),
                'amount': float(expense.get('amount_minor', 0)) / 100,  # Convert to major units
                'category': str(expense.get('category', 'uncategorized') or 'uncategorized').title(),
                'description': expense.get('description', '') or f"{str(expense.get('category', 'uncategorized') or 'uncategorized').title()} expense",
                'date': str(expense.get('created_at', ''))[:10] if expense.get('created_at') and isinstance(expense.get('created_at'), str) else '',  # Extract date part
                'time': str(expense.get('created_at', ''))[11:16] if expense.get('created_at') and isinstance(expense.get('created_at'), str) and len(str(expense.get('created_at', ''))) > 11 else '00:00'  # Extract time part
            })
        
        logger.info(f"PWA entries loaded directly: {len(entries)} entries")
        return render_template('partials/entries.html', entries=entries)
        
    except Exception as e:
        logger.error(f"Error fetching entries directly: {e}")
        # Fallback to empty state - NEVER bypass API endpoints
        return render_template('partials/entries.html', entries=[])

@pwa_ui.route('/ai-chat-test', methods=['POST'])
def ai_chat_test():
    """Simple test endpoint to verify frontend is working"""
    logger.info("Test endpoint hit!")
    return jsonify({
        'success': True,
        'response': 'Test response working! 🎉',
        'expense_logged': False
    })

def finbrain_route(text, user_id):
    """Production router for authenticated users only - no anonymous fallback"""
    from utils.production_router import route_message
    
    assert user_id, "user_id required for expense tracking"
    
    # Call the same production facade that FB Messenger uses
    response_text, intent, category, amount = route_message(
        user_id_hash=user_id,
        text=text,
        channel="web",
        locale="en",
        meta={"source": "ai_chat_authenticated"}
    )
    
    return response_text, intent, category, amount

@pwa_ui.route('/ai-chat', methods=['POST'])
@limiter.limit("8 per minute")
def ai_chat():
    """AI chat endpoint - requires authentication to track expenses"""
    from flask import session
    
    # Get request_id from middleware
    request_id = getattr(g, 'request_id', 'unknown')
    
    # Get session user ID
    session_user_id = session.get('user_id')
    
    # Get resolved user ID from middleware-set g.user_id
    resolved_user_id = getattr(g, 'user_id', None)
    
    # Authentication failure logging (FIX: Remove json.dumps to avoid double-encoding)
    if not resolved_user_id:
        from finbrain.structured import emit_telemetry
        emit_telemetry({
            "request_id": request_id,
            "auth_failed": True,
            "route": "/ai-chat",
            "reason": "unauthenticated"
        })
        return jsonify({"error": "Please log in to track expenses"}), 401
    
    start_time = time.time()
    try:
        data = request.get_json(force=True) or {}
        text = (data.get("text") or data.get("message") or "").strip()
        
        if not text:
            return jsonify({"error": "Message is required"}), 400
        
        # The db_user_id passed to finbrain_route is the same as resolved_user_id
        db_user_id = resolved_user_id
        
        # FIX: Add user_id consistency validation
        user_id_consistent = (session_user_id == resolved_user_id == db_user_id)
        
        # Structured logging at start of handler (FIX: Remove json.dumps to avoid double-encoding)
        try:
            from finbrain.structured import emit_telemetry
        except ImportError:
            emit_telemetry = None
        
        if emit_telemetry:
            emit_telemetry({
            "request_id": request_id,
            "route": "/ai-chat",
            "session_user_id": session_user_id,
            "resolved_user_id": resolved_user_id,
            "db_user_id": db_user_id,
            "user_id_consistent": user_id_consistent,
            "message": text[:40],  # First 40 characters
            "env": "prod"
            })
        
        # FIX: Emit warning if user IDs are inconsistent
        if not user_id_consistent:
            logger.warning(f"User ID inconsistency detected: session={session_user_id}, resolved={resolved_user_id}, db={db_user_id}")

        # Use finbrain AI router with explicit user_id
        logger.info(f"Processing AI chat message for user {resolved_user_id[:8]}***: '{text[:50]}...'")
        reply, intent, category, amount = finbrain_route(text, db_user_id)
        
        # [EXPENSE REPAIR] Apply surgical repair for misclassifications
        from utils.expense_repair import (
            repair_expense_with_fallback,
            safe_normalize_category,
        )
        from utils.feature_flags import expense_repair_enabled
        
        repaired_intent = intent
        repaired_amount = amount
        repaired_category = category
        
        if expense_repair_enabled():
            try:
                repaired_intent, repaired_amount, repaired_category = repair_expense_with_fallback(
                    text=text,
                    original_intent=intent,
                    original_amount=int(amount) if amount is not None else None,
                    original_category=category
                )
                
                # Log repair activity if anything changed
                if (repaired_intent != intent or 
                    repaired_amount != amount or 
                    repaired_category != category):
                    logger.info("expense_repaired: original_intent=%s repaired_intent=%s original_amount=%s repaired_amount=%s original_category=%s repaired_category=%s", 
                               intent, repaired_intent, amount, repaired_amount, category, repaired_category)
                
            except Exception as e:
                logger.warning("repair_system_error: error=%s", str(e))
                # Use normalized category even if repair fails
                repaired_category = safe_normalize_category(category)
        else:
            # Feature disabled - just normalize category
            repaired_category = safe_normalize_category(category)
        
        # Update variables for downstream processing
        intent, amount, category = repaired_intent, repaired_amount, repaired_category
        
        # Check if an expense was successfully saved
        expense_intents = ["expense_logged", "ai_expense_logged", "log_single", "log_expense"]
        expense_id = None
        if intent in expense_intents and amount is not None:
            # FIX: Get the expense_id by looking up the most recent expense for this user
            try:
                from datetime import datetime, timedelta

                from db_base import db
                from models import Expense
                
                # Look for the most recent expense created within the last 5 seconds
                recent_cutoff = datetime.utcnow() - timedelta(seconds=5)
                recent_expense = db.session.query(Expense).filter(
                    Expense.user_id_hash == db_user_id,
                    Expense.created_at >= recent_cutoff,
                    Expense.amount == amount
                ).order_by(Expense.created_at.desc()).first()
                
                if recent_expense:
                    expense_id = recent_expense.id
                    
            except Exception as e:
                logger.warning(f"Could not retrieve expense_id for logging: {e}")
            
            # FIX: Log expense_saved with expense_id and without json.dumps
            if emit_telemetry:
                emit_telemetry({
                    "request_id": request_id,
                    "expense_saved": True,
                    "id": expense_id,  # FIX: Include the primary key as required
                    "amount": amount,
                    "source": "ai-chat",
                    "category": category,
                    "intent": intent
                })
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # FIX: Add success logging with request_id, status=200, latency_ms
        if emit_telemetry:
            emit_telemetry({
                "request_id": request_id,
                "status": 200,
                "latency_ms": latency_ms,
                "route": "/ai-chat",
                "success": True
            })
        
        # [ADDITIVE API] Add new fields while preserving existing contract
        
        # Calculate amount_minor (integer minor units) for new API contract
        amount_minor = None
        if amount is not None:
            try:
                # Convert amount to integer minor units (e.g., 150.00 -> 15000)
                amount_minor = int(float(amount) * 100)
            except (ValueError, TypeError):
                # Fallback: keep amount_minor as None if conversion fails
                amount_minor = None
        
        response_data = {
            "reply": reply,
            "data": {
                "intent": intent or "chat", 
                "category": category or "general", 
                "amount": amount,  # Preserve existing field for backward compatibility
                "amount_minor": amount_minor  # New field: integer minor units (e.g., 15000)
            },
            "user_id": resolved_user_id[:8] + "***",  # Truncated for privacy
            "metadata": {
                "source": "ai-chat",
                "latency_ms": latency_ms
            },
            # New additive fields for enhanced functionality
            "ok": True,
            "mode": "expense" if intent == "add_expense" else "chat",
            "expense_id": expense_id  # Will be None for non-expense intents
        }
        
        return jsonify(response_data), 200
    except Exception as e:
        # FIX: Handle case where resolved_user_id might be None to prevent NameError
        safe_user_id = resolved_user_id[:8] + "***" if resolved_user_id else "unknown"
        logger.error(f"AI chat error for user {safe_user_id}: {type(e).__name__}: {str(e)}")
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log error event
        if emit_telemetry:
            emit_telemetry({
                "request_id": request_id,
                "status": 500,
                "latency_ms": latency_ms,
                "route": "/ai-chat",
                "error": type(e).__name__,
                "success": False
            })
        
        return jsonify({
            "reply": f"Server error: {type(e).__name__}",
            "data": {"intent": "error", "category": None, "amount": None},
            "user_id": safe_user_id,
            "metadata": {
                "source": "ai-chat",
                "latency_ms": latency_ms
            }
        }), 500

@pwa_ui.route('/expense', methods=['POST'])
def add_expense():
    """DEPRECATED: Form submission discontinued - use /ai-chat interface"""
    from datetime import datetime
    
    # Log deprecation attempt for monitoring
    client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
    user_agent = request.headers.get('User-Agent', 'unknown')[:100]
    logger.warning(f"Deprecated /expense form accessed from {client_ip} - User-Agent: {user_agent}")
    
    return jsonify({
        "error": "Form submission discontinued. Use the AI chat interface for expense logging.",
        "status": "service_permanently_discontinued",
        "alternative": "Use /ai-chat endpoint with natural language: 'I spent 100 on lunch'",
        "golden_path": "/ai-chat",
        "timestamp": datetime.utcnow().isoformat(),
        "deprecation_notice": "Form endpoint permanently retired. Web-only architecture active."
    }), 410

# No service worker route - installable but no offline functionality

# Manifest route
@pwa_ui.route('/manifest.webmanifest')
def manifest():
    """PWA manifest file"""
    manifest_data = {
        "name": "finbrain",
        "short_name": "finbrain",
        "start_url": "/",
        "display": "standalone",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }
    
    response = jsonify(manifest_data)
    response.headers['Content-Type'] = 'application/manifest+json'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    
    return response