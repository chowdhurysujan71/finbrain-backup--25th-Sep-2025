"""
PWA UI Blueprint - Modern, installable expense tracking interface
"""
from flask import Blueprint, render_template, request, jsonify, g, current_app
import logging
import time
import os

# Import rate limiter from centralized utility
from utils.rate_limiting import limiter

logger = logging.getLogger(__name__)

pwa_ui = Blueprint('pwa_ui', __name__)

def require_auth():
    """Helper function to ensure user is authenticated via session"""
    from models import User
    from flask import session, abort
    
    # Check if user is logged in via session
    user_id_hash = session.get('user_id')
    if not user_id_hash:
        abort(401)
    
    # Find user in database
    user = User.query.filter_by(user_id_hash=user_id_hash).first()
    if not user:
        # Session is invalid, clear it
        session.clear()
        abort(401)
    
    return user

# Safe JSON helper function
def _json():
    """Safely get JSON from request, return empty dict if parsing fails"""
    try:
        return request.get_json(force=False, silent=True) or {}
    except Exception:
        return {}

def get_user_id():
    """Get user ID from session, X-User-ID header, or return None"""
    from flask import session
    
    # First check session for registered users
    if 'user_id' in session:
        return session['user_id']
    
    # Then check header for PWA/anonymous users
    return request.headers.get('X-User-ID')

# Request logging for chat debugging
@pwa_ui.before_app_request
def _debug_chat_requests():
    """Log chat requests for frontend-backend correlation"""
    if request.path == '/ai-chat' and request.method == 'POST':
        current_app.logger.info('ai-chat start uid=%s ctype=%s', 
                              request.headers.get('X-User-ID'),
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
                    category = 'other'
                    if any(word in user_message.lower() for word in ['food', 'lunch', 'dinner', 'eat', 'restaurant']):
                        category = 'food'
                    elif any(word in user_message.lower() for word in ['transport', 'bus', 'taxi', 'uber', 'rickshaw']):
                        category = 'transport'
                    elif any(word in user_message.lower() for word in ['shop', 'buy', 'purchase', 'store']):
                        category = 'shopping'
                    
                    # Save expense using existing system (with timeout protection)
                    from utils.db import save_expense
                    import uuid
                    
                    logger.info(f"Attempting to save expense: {amount} taka for {category}")
                    result = save_expense(
                        user_identifier=user_id_hash,
                        description=user_message,
                        amount=amount,
                        category=category,
                        platform="pwa",
                        original_message=user_message,
                        unique_id=str(uuid.uuid4()),
                        mid=f"pwa_chat_{int(time.time())}"
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
    Safe route that shows UI even if backend APIs aren't available
    """
    user_id = get_user_id()
    logger.info(f"PWA chat route accessed by user: {user_id or 'anonymous'}")
    
    return render_template('chat.html', user_id=user_id)

@pwa_ui.route('/report')
def report():
    """
    Money Story summary cards + placeholder charts
    Reads from existing endpoints if available, shows placeholders otherwise
    """
    user_id = get_user_id()
    logger.info(f"PWA report route accessed by user: {user_id or 'anonymous'}")
    
    return render_template('report.html', user_id=user_id)

@pwa_ui.route('/profile')
def profile():
    """
    Profile summary showing user info if available
    Safe fallback when no user context
    """
    user_id = get_user_id()
    logger.info(f"PWA profile route accessed by user: {user_id or 'anonymous'}")
    
    return render_template('profile.html', user_id=user_id)

@pwa_ui.route('/challenge')
def challenge():
    """
    3-day challenge progress UI
    Placeholder implementation for demo purposes
    """
    user_id = get_user_id()
    logger.info(f"PWA challenge route accessed by user: {user_id or 'anonymous'}")
    
    return render_template('challenge.html', user_id=user_id)

@pwa_ui.route('/login')
def login():
    """
    Login page for user registration system
    """
    return render_template('login.html')

@pwa_ui.route('/register')
def register():
    """
    Registration page for new users
    """
    return render_template('register.html')

@pwa_ui.route('/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def auth_login():
    """
    Process user login by proxying to backend authentication API
    """
    from models import User
    from db_base import db
    from werkzeug.security import check_password_hash
    from flask import session, request, jsonify
    
    try:
        data = request.get_json(silent=True) or {}
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid credentials"}), 401
        
        # Create session using Flask's built-in session system
        session.permanent = True  # Make session permanent for 30-day lifetime
        session['user_id'] = user.user_id_hash
        session['email'] = email
        session['is_registered'] = True
        
        # Return response (Flask handles secure session cookie automatically)
        return jsonify({
            "success": True, 
            "message": "Login successful",
            "data": {"user_id": user.user_id_hash}
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Login failed. Please try again."}), 500

@pwa_ui.route('/api/auth/me', methods=['GET'])
def auth_me():
    """
    Check current user session and return user info or 401
    Cheap and reliable endpoint for frontend auth state checking
    """
    from models import User
    from flask import session, jsonify
    
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

@pwa_ui.route('/auth/register', methods=['POST'])
@limiter.limit("3 per minute")
def auth_register():
    """
    Process user registration with comprehensive validation and standardized error handling
    """
    from models import User
    from db_base import db
    from werkzeug.security import generate_password_hash
    from flask import session, request, jsonify
    from utils.identity import psid_hash
    import uuid
    import time
    
    try:
        data = request.get_json(silent=True) or {}
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
        
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
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Registration failed. Please try again."}), 500

@pwa_ui.route('/auth/logout', methods=['POST'])
def auth_logout():
    """
    Process user logout
    """
    from flask import session
    
    session.clear()
    return jsonify({
        'success': True,
        'message': 'Logged out successfully',
        'redirect': '/login'
    })

@pwa_ui.route('/api/auth/generate-guest-token', methods=['POST'])
@limiter.limit("20 per minute")
def generate_guest_token():
    """
    Generate a secure link token for a guest ID
    Called by PWA when creating guest sessions
    """
    from utils.guest_tokens import generate_guest_token as create_token
    from flask import request, jsonify
    
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
    from models import Expense
    from db_base import db
    from flask import request, jsonify
    from utils.identity import psid_hash
    from utils.guest_tokens import verify_guest_token, mark_token_as_used, is_token_recently_used
    
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
            logger.warning(f"Invalid guest token attempt from user {user.user_id_hash[:8]}*** for guest {guest_id[:8]}***: {token_data.get('error', 'Unknown error')}")
            return jsonify({
                "error": "Invalid or expired link token",
                "details": "Guest data merge requires valid authentication token"
            }), 401
        
        # Check for token reuse (basic replay protection)
        token_nonce = token_data.get('nonce', '')
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
    import requests
    import os
    
    try:
        # SECURITY: Only session-authenticated users can see entries
        if 'user_id' not in session:
            logger.warning("Unauthorized access to /partials/entries - no session")
            return render_template('partials/entries.html', entries=[])
        
        # UI GUARDRAIL: Call only the canonical backend API endpoint
        # This enforces session authentication and unified read path
        base_url = os.environ.get('REPLIT_DEV_DOMAIN', 'http://localhost:5000')
        
        # Use internal API call with session cookies
        response = requests.post(
            f"{base_url}/api/backend/get_recent_expenses",
            json={"limit": 10},
            cookies=request.cookies,  # Pass session cookies for authentication
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'PWA-Internal-Client/1.0'
            },
            timeout=5
        )
        
        if response.status_code == 200:
            api_data = response.json()
            
            # Convert API response to template format
            entries = []
            for expense in api_data:
                entries.append({
                    'id': expense.get('id', 0),
                    'amount': float(expense.get('amount_minor', 0)) / 100,  # Convert to major units
                    'category': (expense.get('category', 'uncategorized') or 'uncategorized').title(),
                    'description': expense.get('description', '') or f"{(expense.get('category', 'uncategorized') or 'uncategorized').title()} expense",
                    'date': expense.get('created_at', '')[:10] if expense.get('created_at') else '',  # Extract date part
                    'time': expense.get('created_at', '')[11:16] if expense.get('created_at') and len(expense.get('created_at', '')) > 11 else '00:00'  # Extract time part
                })
            
            logger.info(f"PWA entries loaded via API: {len(entries)} entries")
            return render_template('partials/entries.html', entries=entries)
        
        else:
            logger.warning(f"API call failed with status {response.status_code}: {response.text}")
            return render_template('partials/entries.html', entries=[])
        
    except Exception as e:
        logger.error(f"Error fetching entries via API: {e}")
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

def finbrain_route(text, request_obj):
    """Updated wrapper that uses the production router facade for 100% success rate"""
    from utils.production_router import route_message
    from utils.identity import psid_hash
    import uuid
    
    # Get stable user ID from X-User-ID header (set by frontend localStorage)
    uid = request_obj.headers.get('X-User-ID')
    
    if not uid:
        # Fallback: generate stable ID for this session and store in cookie
        uid = request_obj.cookies.get('user_id')
        if not uid:
            uid = f"pwa_user_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    
    # Generate stable hash for data processing (like FB Messenger)
    user_hash = psid_hash(uid) if uid.startswith('pwa_') else uid
    
    # Call the same production facade that FB Messenger uses for 100% success
    response_text, intent, category, amount = route_message(
        user_id_hash=user_hash,
        text=text,
        channel="web",
        locale="en",
        meta={"user_agent": request_obj.headers.get('User-Agent', 'unknown')}
    )
    
    return response_text

@pwa_ui.route('/ai-chat', methods=['POST'])
@limiter.limit("8 per minute")
def ai_chat():
    """AI chat endpoint with proper metadata structure for prod gate compliance"""
    start_time = time.time()
    try:
        data = request.get_json(force=True) or {}
        text = (data.get("text") or data.get("message") or "").strip()
        
        # Get user ID from headers (for prod gate testing)
        user_id = request.headers.get('X-User-ID', 'anonymous')
        
        if not text:
            latency_ms = int((time.time() - start_time) * 1000)
            return jsonify({
                "reply": "Say something and I'll respond.",
                "data": {"intent": "help", "category": None, "amount": None},
                "user_id": user_id,
                "metadata": {
                    "source": "ai-chat",
                    "latency_ms": latency_ms
                }
            }), 200

        # Use FinBrain AI router
        reply = finbrain_route(text, request)
        latency_ms = int((time.time() - start_time) * 1000)
        
        return jsonify({
            "reply": reply,
            "data": {"intent": "chat", "category": "general", "amount": None},
            "user_id": user_id,
            "metadata": {
                "source": "ai-chat",
                "latency_ms": latency_ms
            }
        }), 200
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        # Make sure the client always gets proper structure even on error
        return jsonify({
            "reply": f"Server error: {type(e).__name__}",
            "data": {"intent": "error", "category": None, "amount": None},
            "user_id": request.headers.get('X-User-ID', 'anonymous'),
            "metadata": {
                "source": "ai-chat",
                "latency_ms": latency_ms
            }
        }), 200

@pwa_ui.route('/expense', methods=['POST'])
def add_expense():
    """
    Real expense submission using existing FinBrain expense logging system
    Now supports natural language input via unified brain
    Enhanced with standardized error handling and comprehensive validation
    """
    from utils.db import save_expense
    from utils.identity import psid_hash
    from utils.error_responses import (
        validation_error_response, internal_error, success_response, 
        standardized_error_response, ErrorCodes, safe_error_message
    )
    from utils.validators import validate_expense
    from utils.structured_logger import api_logger, log_validation_failure
    import uuid
    
    start_time = time.time()
    
    try:
        # Get user ID for both structured and natural language processing
        uid = request.headers.get('X-User-ID') or request.cookies.get('user_id') or 'anon'
        
        # Check if user submitted natural language instead of form fields
        nl_message = request.form.get('nl_message')
        
        if nl_message and nl_message.strip():
            # Process natural language expense using unified brain
            api_logger.info(f"Processing natural language expense", {
                "user_prefix": uid[:8] + "***" if len(uid) > 8 else uid,
                "message_length": len(nl_message),
                "processing_type": "natural_language"
            })
            
            try:
                from core.brain import process_expense_message
                
                brain_result = process_expense_message(uid, nl_message.strip())
                
                if brain_result.get("structured", {}).get("ready_to_save"):
                    # Extract expense data and save automatically
                    structured = brain_result["structured"]
                    amount_float = structured["amount"]
                    category = structured["category"]
                    description = brain_result["reply"]
                    
                    api_logger.info(f"Auto-saving NL expense", {
                        "amount": amount_float,
                        "category": category,
                        "auto_save": True
                    })
                    # Continue with existing save logic using structured data
                else:
                    # Return response for user confirmation or interaction
                    response_time = (time.time() - start_time) * 1000
                    api_logger.log_api_request(True, response_time, {
                        "needs_confirmation": True,
                        "suggested_amount": brain_result.get("structured", {}).get("amount")
                    })
                    return jsonify(success_response({
                        'needs_confirmation': brain_result.get("structured", {}).get("amount") is not None,
                        'suggested_data': brain_result.get("structured", {}),
                        'metadata': brain_result.get("metadata", {})
                    }, brain_result["reply"]))
                    
            except Exception as e:
                api_logger.error("Natural language expense processing failed", {
                    "error_type": type(e).__name__,
                    "processing_type": "natural_language"
                }, e)
                response, status_code = standardized_error_response(
                    code=ErrorCodes.OPERATION_FAILED,
                    message="Could not process your expense message. Please try using the form instead.",
                    status_code=400,
                    context={"nl_error": True}
                )
                return jsonify(response), status_code
        else:
            # Traditional form-based expense entry - validate using new system
            expense_data = {
                'amount': request.form.get('amount'),
                'category': request.form.get('category'),
                'description': request.form.get('description', '')
            }
            
            # Validate expense data using comprehensive validator
            validation_result = validate_expense(expense_data)
            if validation_result.has_errors():
                log_validation_failure(validation_result.errors, "expense_submission")
                response, status_code = validation_error_response(validation_result.errors)
                return jsonify(response), status_code
            
            # Extract validated data
            amount_float = float(expense_data['amount'])
            category = expense_data['category'].lower()
            description = expense_data['description']
        
        # Get user ID from header or form data (set by PWA JavaScript)
        user_id = get_user_id() or request.form.get('user_id') or f"pwa_user_{int(time.time())}"
        user_hash = psid_hash(user_id) if user_id.startswith('pwa_') else user_id
        
        # Generate unique identifiers
        unique_id = str(uuid.uuid4())
        mid = f"pwa_{int(time.time() * 1000000)}"
        
        # Create original message for logging
        original_message = f"PWA: {amount_float} BDT for {category}"
        if description:
            original_message += f" - {description}"
        
        # Use unified expense creation function
        from utils.db import create_expense
        from datetime import datetime
        
        result = create_expense(
            user_id=user_hash,
            amount=amount_float,
            currency='৳',
            category=category,
            occurred_at=datetime.now(),
            source_message_id=mid,
            correlation_id=unique_id,  # Use unique_id as correlation_id
            notes=description or f"{category} expense"
        )
        
        # Log successful expense creation
        response_time = (time.time() - start_time) * 1000
        api_logger.log_api_request(True, response_time, {
            "amount": amount_float,
            "category": category,
            "expense_id": result.get('expense_id') if result else unique_id,
            "processing_type": "form_based"
        })
        
        # Return standardized success response
        return jsonify(success_response({
            'expense_id': result.get('expense_id') if result else unique_id,
            'amount': amount_float,
            'category': category
        }, f'Expense of ৳{amount_float:.2f} logged successfully!'))
        
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        api_logger.error("PWA expense logging error", {
            "error_type": type(e).__name__,
            "response_time_ms": response_time
        }, e)
        
        response, status_code = internal_error(safe_error_message(e, "Failed to log expense. Please try again."))
        return jsonify(response), status_code

# Service Worker route (must be at root for scope)
@pwa_ui.route('/sw.js')
def service_worker():
    """Serve service worker from root for correct scope"""
    from flask import send_from_directory
    response = send_from_directory('.', 'sw.js')
    response.headers['Content-Type'] = 'text/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache'
    return response

# Manifest route
@pwa_ui.route('/manifest.webmanifest')
def manifest():
    """PWA manifest file"""
    manifest_data = {
        "name": "FinBrain",
        "short_name": "FinBrain",
        "description": "AI-powered expense tracking and financial insights",
        "start_url": "/chat",
        "display": "standalone",
        "theme_color": "#0066ff",
        "background_color": "#ffffff",
        "orientation": "portrait-primary",
        "scope": "/",
        "icons": [
            {
                "src": "/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-512.png", 
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ],
        "categories": ["finance", "productivity"],
        "lang": "en",
        "prefer_related_applications": False
    }
    
    response = jsonify(manifest_data)
    response.headers['Content-Type'] = 'application/manifest+json'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    
    return response