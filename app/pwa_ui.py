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
    Recent entries partial for HTMX
    Shows demo data or fetches from existing APIs if available
    """
    user_id = get_user_id()
    
    # Demo entries for UI development
    # In production, this would fetch from existing expense endpoints
    demo_entries = [
        {
            'id': 1,
            'amount': 45.50,
            'category': 'Food',
            'description': 'Lunch at cafe',
            'date': '2025-09-08',
            'time': '12:30'
        },
        {
            'id': 2,
            'amount': 12.99,
            'category': 'Transport',
            'description': 'Bus fare',
            'date': '2025-09-08',
            'time': '09:15'
        }
    ]
    
    return render_template('partials/entries.html', entries=demo_entries)

@pwa_ui.route('/expense', methods=['POST'])
def add_expense():
    """
    Safe expense submission that shows success without breaking anything
    Returns demo response until backend endpoints are wired
    """
    user_id = get_user_id()
    data = request.get_json() or {}
    
    # Log the expense attempt
    logger.info(f"PWA expense submission by user {user_id}: {data}")
    
    # Demo response - in production this would integrate with existing expense logging
    demo_mode = os.environ.get('PWA_DEMO_MODE', '1') == '1'
    
    if demo_mode:
        return jsonify({
            'success': True,
            'message': 'Expense logged (demo mode)',
            'expense_id': f'demo_{int(time.time())}'
        }), 201
    else:
        # When ready to integrate with existing backend:
        # - Import existing expense handlers
        # - Route to existing business logic  
        # - Return real response
        return jsonify({
            'success': False,
            'message': 'Expense logging not yet connected to backend'
        }), 503

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
        ]
    }
    
    response = jsonify(manifest_data)
    response.headers['Content-Type'] = 'application/manifest+json'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    
    return response