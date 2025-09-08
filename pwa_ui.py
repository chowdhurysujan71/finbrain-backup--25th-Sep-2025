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
    """Get user ID from X-User-ID header or return None"""
    return request.headers.get('X-User-ID')

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