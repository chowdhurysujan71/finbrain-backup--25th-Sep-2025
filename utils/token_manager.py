"""Facebook Page Access Token management with refresh monitoring"""
import os
import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class TokenManager:
    """Manages Facebook Page Access Token lifecycle and refresh scheduling"""
    
    def __init__(self):
        self.page_access_token = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")
        self.app_id = os.environ.get("FACEBOOK_APP_ID", "")
        self.app_secret = os.environ.get("FACEBOOK_APP_SECRET", "")
        self._token_info_cache = None
        self._cache_expires = 0
        
    def get_token_info(self) -> Optional[Dict]:
        """Get current token information from Facebook Graph API"""
        if not self.page_access_token:
            logger.error("No page access token configured")
            return None
            
        # Use cache if still valid (refresh every 5 minutes)
        current_time = time.time()
        if self._token_info_cache and current_time < self._cache_expires:
            return self._token_info_cache
            
        try:
            url = f"https://graph.facebook.com/v17.0/me"
            params = {
                'fields': 'id,name',
                'access_token': self.page_access_token
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Get token expiration info using debug_token
                debug_url = f"https://graph.facebook.com/v17.0/debug_token"
                debug_params = {
                    'input_token': self.page_access_token,
                    'access_token': f"{self.app_id}|{self.app_secret}"
                }
                
                debug_response = requests.get(debug_url, params=debug_params, timeout=10)
                
                if debug_response.status_code == 200:
                    debug_data = debug_response.json().get('data', {})
                    
                    # Combine token info
                    token_info = {
                        'page_id': token_data.get('id'),
                        'page_name': token_data.get('name'),
                        'token_valid': debug_data.get('is_valid', False),
                        'expires_at': debug_data.get('expires_at'),
                        'issued_at': debug_data.get('issued_at'),
                        'scopes': debug_data.get('scopes', []),
                        'app_id': debug_data.get('app_id'),
                        'type': debug_data.get('type'),
                        'last_checked': datetime.utcnow().isoformat()
                    }
                    
                    # Cache for 5 minutes
                    self._token_info_cache = token_info
                    self._cache_expires = current_time + 300
                    
                    return token_info
                else:
                    logger.error(f"Failed to debug token: {debug_response.status_code}")
                    return None
                    
            else:
                logger.error(f"Failed to get token info: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting token info: {str(e)}")
            return None
    
    def check_token_expiry(self) -> Tuple[bool, Optional[datetime], Optional[str]]:
        """
        Check if token is expiring soon
        Returns: (needs_refresh, expires_at, warning_message)
        """
        token_info = self.get_token_info()
        
        if not token_info:
            return True, None, "Token info unavailable - check configuration"
        
        if not token_info.get('token_valid'):
            return True, None, "Token is invalid - immediate refresh required"
        
        expires_at = token_info.get('expires_at')
        if not expires_at:
            # Permanent token or long-lived token without expiry
            return False, None, "Token appears to be permanent"
        
        # Convert timestamp to datetime
        try:
            expiry_date = datetime.fromtimestamp(expires_at)
            now = datetime.now()
            days_until_expiry = (expiry_date - now).days
            
            # Warn if expiring within 7 days
            if days_until_expiry <= 7:
                warning = f"Token expires in {days_until_expiry} days ({expiry_date.strftime('%Y-%m-%d')})"
                return True, expiry_date, warning
            elif days_until_expiry <= 30:
                warning = f"Token expires in {days_until_expiry} days ({expiry_date.strftime('%Y-%m-%d')})"
                return False, expiry_date, warning
            else:
                return False, expiry_date, f"Token expires on {expiry_date.strftime('%Y-%m-%d')}"
                
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing token expiry: {str(e)}")
            return True, None, "Unable to parse token expiry date"
    
    def get_token_status_summary(self) -> Dict:
        """Get comprehensive token status for monitoring"""
        token_info = self.get_token_info()
        needs_refresh, expires_at, message = self.check_token_expiry()
        
        status = {
            'token_configured': bool(self.page_access_token),
            'app_secret_configured': bool(self.app_secret),
            'app_id_configured': bool(self.app_id),
            'token_valid': False,
            'needs_refresh': needs_refresh,
            'status_message': message or "Token status unknown",
            'last_checked': datetime.utcnow().isoformat()
        }
        
        if token_info:
            status.update({
                'token_valid': token_info.get('token_valid', False),
                'page_id': token_info.get('page_id'),
                'page_name': token_info.get('page_name'),
                'token_type': token_info.get('type'),
                'scopes': token_info.get('scopes', [])
            })
            
            if expires_at:
                status['expires_at'] = expires_at.isoformat()
        
        return status

# Global token manager instance
token_manager = TokenManager()

def get_token_status() -> Dict:
    """Get current token status - convenience function"""
    return token_manager.get_token_status_summary()

def check_token_health() -> Tuple[bool, str]:
    """
    Quick health check for token
    Returns: (is_healthy, status_message)
    """
    try:
        status = token_manager.get_token_status_summary()
        
        if not status['token_configured']:
            return False, "No page access token configured"
        
        if not status['token_valid']:
            return False, "Token is invalid"
        
        if status['needs_refresh']:
            return False, f"Token needs refresh: {status['status_message']}"
        
        return True, status['status_message']
        
    except Exception as e:
        return False, f"Token health check failed: {str(e)}"