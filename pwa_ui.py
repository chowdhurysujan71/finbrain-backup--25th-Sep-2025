"""
PWA UI Blueprint - Modern, installable expense tracking interface
"""
from flask import Blueprint, render_template, request, jsonify, g
import logging
import time
import os

logger = logging.getLogger(__name__)

pwa_ui = Blueprint('pwa_ui', __name__)

def get_user_id():
    """Get user ID from session, X-User-ID header, or return None"""
    from flask import session
    
    # First check session for registered users
    if 'user_id' in session:
        return session['user_id']
    
    # Then check header for PWA/anonymous users
    return request.headers.get('X-User-ID')

def handle_with_fallback_ai(user_message, user_id_hash, conversational_ai):
    """Handle chat message using fallback AI when main router is unavailable"""
    try:
        # Check if message is about expenses
        if any(word in user_message.lower() for word in ['spent', 'taka', '৳', 'cost', 'paid', 'bought', 'expense']):
            # Try to parse expense from message
            try:
                from ai.expense_parse import parse_expense
                parsed = parse_expense(user_message)
                
                # Save expense using existing system
                from utils.db import save_expense
                import uuid
                result = save_expense(
                    user_identifier=user_id_hash,
                    description=parsed.get('note', 'PWA expense'),
                    amount=float(parsed.get('amount', 0)),
                    category=parsed.get('category', 'other'),
                    platform="pwa",
                    original_message=user_message,
                    unique_id=str(uuid.uuid4()),
                    mid=f"pwa_chat_{int(time.time())}"
                )
                return f"✅ Logged expense: ৳{parsed.get('amount')} for {parsed.get('category')}"
            except Exception as e:
                logger.warning(f"Expense parsing failed: {e}")
                return "I understand you want to log an expense. Please use the format: 'I spent 100 taka on food'"
        else:
            # General conversation using conversational AI if available
            if conversational_ai:
                try:
                    context = conversational_ai.get_user_expense_context(user_id_hash, 30)
                    response = conversational_ai.generate_response(user_message, context)
                    return response
                except Exception as e:
                    logger.warning(f"Conversational AI failed: {e}")
            
            # Final fallback
            return "I'm your AI expense assistant! Try saying things like 'I spent 200 taka on lunch' or 'Show my spending summary'"
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
def auth_login():
    """
    Process user login
    """
    from models import User
    from app import db
    from werkzeug.security import check_password_hash
    from flask import session
    from utils.identity import psid_hash
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
        
        # Create session
        session['user_id'] = user.user_id_hash
        session['email'] = user.email
        session['is_registered'] = True
        
        logger.info(f"User logged in successfully: {email}")
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'redirect': '/chat'
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            'success': False,
            'error': 'Login failed. Please try again.'
        }), 500

@pwa_ui.route('/auth/register', methods=['POST'])
def auth_register():
    """
    Process user registration
    """
    from models import User
    from app import db
    from werkzeug.security import generate_password_hash
    from flask import session
    from utils.identity import psid_hash
    import uuid
    
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        name = data.get('name', '')
        
        if not email or not password:
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'An account with this email already exists'
            }), 409
        
        # Generate user hash
        user_id = f"pwa_reg_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        user_hash = psid_hash(user_id)
        
        # Create new user
        user = User(
            user_id_hash=user_hash,
            email=email,
            password_hash=generate_password_hash(password),
            first_name=name,
            platform='pwa'
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Create session
        session['user_id'] = user_hash
        session['email'] = email
        session['is_registered'] = True
        
        logger.info(f"User registered successfully: {email}")
        
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'redirect': '/chat'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration error: {e}")
        return jsonify({
            'success': False,
            'error': 'Registration failed. Please try again.'
        }), 500

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
    Recent entries partial for HTMX - shows real user expenses
    """
    from models import Expense
    from utils.identity import psid_hash
    from app import db
    
    try:
        # Get user ID from header (set by PWA JavaScript)
        user_id = get_user_id()
        if user_id:
            user_hash = psid_hash(user_id) if user_id.startswith('pwa_') else user_id
            logger.info(f"PWA entries lookup for user {user_hash[:8]}...")
            
            # Query recent expenses for this user
            recent_expenses = db.session.query(Expense)\
                .filter_by(user_id_hash=user_hash)\
                .order_by(Expense.created_at.desc())\
                .limit(10)\
                .all()
            
            # Convert to template-friendly format
            entries = []
            for exp in recent_expenses:
                entries.append({
                    'id': exp.id,
                    'amount': float(exp.amount),
                    'category': exp.category.title(),
                    'description': exp.description or f"{exp.category.title()} expense",
                    'date': exp.date.strftime('%Y-%m-%d'),
                    'time': exp.time.strftime('%H:%M') if exp.time else '00:00'
                })
            
            return render_template('partials/entries.html', entries=entries)
        
    except Exception as e:
        logger.error(f"Error fetching entries: {e}")
    
    # Fallback to empty state
    return render_template('partials/entries.html', entries=[])

@pwa_ui.route('/ai-chat', methods=['POST'])
def ai_chat():
    """AI chat endpoint that processes natural language and connects to main FinBrain AI system"""
    # Import dependencies
    from utils.identity import psid_hash
    import json
    
    # Initialize production router with fallback
    route_message = None
    try:
        from utils.production_router import route_message
    except ImportError:
        logger.warning("Production router not available, using fallback")
        route_message = None
    
    # Always initialize fallback AI
    conversational_ai = None
    try:
        from utils.conversational_ai import ConversationalAI
        conversational_ai = ConversationalAI()
    except ImportError:
        logger.warning("Conversational AI not available")
    
    user_id = get_user_id()
    
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'User identification required'
        }), 400
    
    try:
        # Get message from request
        data = request.get_json()
        if not data or not data.get('message'):
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Please enter a message'
            }), 400
        
        # Hash user ID for processing (consistent with main system)
        user_id_hash = psid_hash(user_id)
        
        logger.info(f"AI chat request from user {user_id_hash[:8]}...: '{user_message[:50]}...'")
        
        # Use the main FinBrain AI routing system with robust fallbacks
        response_data = None
        
        if route_message:
            try:
                logger.info(f"Using production router for user {user_id_hash[:8]}")
                response_data = route_message(user_id_hash, user_message)
                logger.info(f"Production router response: {str(response_data)[:100]}...")
            except Exception as e:
                logger.warning(f"Production router failed: {e}")
                response_data = None
        
        # If production router failed or unavailable, use fallback
        if response_data is None:
            logger.info(f"Using fallback AI for user {user_id_hash[:8]}")
            response_data = handle_with_fallback_ai(user_message, user_id_hash, conversational_ai)
        
        # Check if an expense was logged
        expense_logged = ('✅' in str(response_data) or 
                         ('expense' in response_data.get('actions', []) if isinstance(response_data, dict) else False))
        
        # Format response for PWA interface
        if isinstance(response_data, dict):
            ai_response = response_data.get('message', response_data.get('response', str(response_data)))
        else:
            ai_response = str(response_data)
        
        # Clean up the response for chat interface
        if ai_response.startswith('✅'):
            ai_response = ai_response.replace('✅', '✅')
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'expense_logged': expense_logged
        })
        
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return jsonify({
            'success': True,  # Don't fail the UI
            'response': 'I had a brief connection issue. Please try again! 🤖',
            'expense_logged': False
        })

@pwa_ui.route('/expense', methods=['POST'])
def add_expense():
    """
    Real expense submission using existing FinBrain expense logging system
    """
    from utils.db import save_expense
    from utils.identity import psid_hash
    import uuid
    
    try:
        # Get form data (not JSON since it's a regular HTML form)
        amount = request.form.get('amount')
        category = request.form.get('category')
        description = request.form.get('description', '')
        
        # Validate required fields
        if not amount or not category:
            return jsonify({
                'success': False,
                'message': 'Amount and category are required'
            }), 400
        
        # Convert amount to float and validate
        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError("Amount must be positive")
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Please enter a valid amount'
            }), 400
        
        # Get user ID from header or form data (set by PWA JavaScript)
        user_id = get_user_id() or request.form.get('user_id') or f"pwa_user_{int(time.time())}"
        user_hash = psid_hash(user_id) if user_id.startswith('pwa_') else user_id
        
        # Generate unique identifiers
        unique_id = str(uuid.uuid4())
        mid = f"pwa_{int(time.time() * 1000000)}"
        
        # Create original message for logging
        original_message = f"PWA: {amount} BDT for {category}"
        if description:
            original_message += f" - {description}"
        
        # Use existing expense logging system
        result = save_expense(
            user_identifier=user_hash,
            description=description or f"{category} expense",
            amount=amount_float,
            category=category.lower(),
            platform="pwa",
            original_message=original_message,
            unique_id=unique_id,
            mid=mid
        )
        
        logger.info(f"PWA expense logged successfully for user {user_hash[:8]}... (original_id: {user_id})")
        
        # Return success message as plain text for HTMX to display
        return jsonify({
            'success': True,
            'message': f'Expense of ৳{amount_float:.2f} logged successfully!',
            'expense_id': result.get('expense_id') if result else unique_id
        }), 200
        
    except Exception as e:
        logger.error(f"PWA expense logging error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Failed to log expense. Please try again.'
        }), 500

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