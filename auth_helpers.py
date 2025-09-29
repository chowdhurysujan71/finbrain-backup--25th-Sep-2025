"""
Centralized authentication helpers for single-source-of-truth user context
Includes subdomain-based authentication for finbrain.app
"""
import logging
from urllib.parse import urlparse

from flask import g, request, session

logger = logging.getLogger(__name__)

def get_user_id_from_session():
    """
    Get authenticated user ID from session (server-side only)
    Returns None for anonymous users
    
    This is the ONLY function that should read session data for user identity.
    All other code should use Flask's g.user_id
    """
    try:
        # Check session for authenticated users
        user_id = session.get('user_id')
        if user_id and len(user_id) > 10:  # Basic validation
            logger.debug(f"Session user found: {user_id[:8]}***")
            return user_id
        
        logger.debug("No authenticated session found")
        return None
        
    except Exception as e:
        logger.error(f"Session read error: {e}")
        return None

def require_authenticated_user():
    """
    Ensure current request has authenticated user
    Returns user_id or raises ValueError
    """
    user_id = getattr(g, 'user_id', None)
    if not user_id:
        raise ValueError("Authentication required")
    return user_id

def is_authenticated():
    """
    Check if current request has authenticated user
    Returns True/False
    """
    return getattr(g, 'user_id', None) is not None

def get_subdomain():
    """
    Parse subdomain from request.host for finbrain.app and replit domain routing
    
    Returns:
        str: Subdomain name ('app', 'login', 'report', etc.) or 'www' for root domain
        None: For localhost or unrecognized domains
    
    Examples:
        app.finbrain.app -> 'app'
        login.finbrain.app -> 'login' 
        finbrain.app -> 'www'
        localhost:5000 -> None
        replit.dev/app -> 'app' (from path-based routing)
    """
    import os
    
    try:
        host = request.host.lower()
        
        # Handle localhost and development environments
        if 'localhost' in host or '127.0.0.1' in host or not host:
            return None
            
        # Handle finbrain.app domains (production)
        if '.finbrain.app' in host:
            # Extract subdomain from host like "app.finbrain.app"
            subdomain = host.split('.finbrain.app')[0]
            
            # Handle multiple subdomains (e.g., "api.app.finbrain.app" -> "api.app")
            if '.' in subdomain:
                return subdomain.split('.')[-1]  # Return the last part before finbrain.app
            
            return subdomain if subdomain else 'www'
        
        # Handle root domain finbrain.app
        if host == 'finbrain.app':
            return 'www'
            
        # Handle replit domains for testing
        replit_domains = os.environ.get('REPLIT_DOMAINS', '')
        if replit_domains and (host in replit_domains or 'replit.dev' in host or 'replit.app' in host):
            # For replit domains, extract subdomain from path if available
            # Since replit doesn't support real subdomains, we'll use path-based routing
            path = getattr(request, 'path', '/')
            if path.startswith('/app'):
                return 'app'
            elif path.startswith('/login'):
                return 'login'
            elif path.startswith('/report'):
                return 'report'
            elif path.startswith('/profile'):
                return 'profile'
            elif path.startswith('/challenge'):
                return 'challenge'
            else:
                return 'www'  # Default for replit domains
            
        # Non-recognized domains
        return None
        
    except Exception as e:
        logger.warning(f"Failed to parse subdomain from host: {e}")
        return None

def get_feature_subdomains():
    """
    Get list of subdomains that require authentication
    """
    return ['app', 'report', 'profile', 'challenge']

def is_protected_subdomain(subdomain):
    """
    Check if subdomain requires authentication
    
    Args:
        subdomain: Subdomain to check
        
    Returns:
        bool: True if subdomain requires authentication
    """
    return subdomain in get_feature_subdomains()

def validate_return_to_url(return_to):
    """
    Validate returnTo parameter for security
    Only allows local paths and trusted domains to prevent open redirect attacks
    
    Args:
        return_to: The returnTo URL parameter
        
    Returns:
        bool: True if URL is safe to redirect to
    """
    import os
    
    if not return_to:
        return False
        
    try:
        # Parse the URL
        parsed = urlparse(return_to)
        
        # Only allow relative paths (no scheme, no netloc)
        if parsed.scheme or parsed.netloc:
            # Allow finbrain.app subdomains (production)
            if parsed.netloc.endswith('.finbrain.app') or parsed.netloc == 'finbrain.app':
                return True
                
            # Allow replit domains for testing
            replit_domains = os.environ.get('REPLIT_DOMAINS', '')
            if replit_domains and (parsed.netloc in replit_domains or 
                                 'replit.dev' in parsed.netloc or 
                                 'replit.app' in parsed.netloc):
                return True
                
            # Block all other external domains
            return False
                
        # Don't allow javascript: or data: URLs
        if return_to.lower().startswith(('javascript:', 'data:', 'vbscript:')):
            return False
            
        # Basic path validation - must start with /
        if not return_to.startswith('/') and not return_to.startswith('http'):
            return False
            
        return True
        
    except Exception as e:
        logger.warning(f"Failed to validate returnTo URL: {e}")
        return False