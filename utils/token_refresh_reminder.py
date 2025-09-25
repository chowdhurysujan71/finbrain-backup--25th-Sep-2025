"""Token refresh reminder and monitoring system"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from .token_manager import token_manager

logger = logging.getLogger(__name__)

class TokenRefreshReminder:
    """Monitor and remind about Facebook Page Access Token refresh needs"""
    
    def __init__(self):
        self.reminder_thresholds = {
            'critical': 3,    # 3 days or less
            'warning': 7,     # 7 days or less
            'notice': 30      # 30 days or less
        }
    
    def check_all_tokens(self) -> dict:
        """Check all token status and generate appropriate reminders"""
        results = {
            'status': 'healthy',
            'reminders': [],
            'actions_needed': [],
            'next_check_recommended': datetime.now() + timedelta(hours=24),
            'last_checked': datetime.now().isoformat()
        }
        
        try:
            # Check main page access token
            needs_refresh, expires_at, message = token_manager.check_token_expiry()
            token_info = token_manager.get_token_status_summary()
            
            if not token_info['token_configured']:
                results['status'] = 'critical'
                results['actions_needed'].append({
                    'priority': 'critical',
                    'action': 'configure_token',
                    'message': 'Facebook Page Access Token not configured',
                    'instructions': [
                        'Go to Facebook Developer Console',
                        'Generate a Page Access Token for your app',
                        'Set FACEBOOK_PAGE_ACCESS_TOKEN environment variable',
                        'Restart the application'
                    ]
                })
                return results
            
            if not token_info['token_valid']:
                results['status'] = 'critical'
                results['actions_needed'].append({
                    'priority': 'critical',
                    'action': 'refresh_invalid_token',
                    'message': 'Facebook Page Access Token is invalid',
                    'instructions': [
                        'Check if the token was revoked in Facebook Developer Console',
                        'Generate a new Page Access Token',
                        'Update FACEBOOK_PAGE_ACCESS_TOKEN environment variable',
                        'Test webhook connectivity'
                    ]
                })
                return results
            
            if needs_refresh and expires_at:
                days_until_expiry = (expires_at - datetime.now()).days
                
                if days_until_expiry <= self.reminder_thresholds['critical']:
                    results['status'] = 'critical'
                    results['actions_needed'].append({
                        'priority': 'critical',
                        'action': 'refresh_expiring_token',
                        'message': f'Token expires in {days_until_expiry} days',
                        'expires_at': expires_at.isoformat(),
                        'instructions': [
                            'URGENT: Go to Facebook Developer Console immediately',
                            'Generate a new long-lived Page Access Token',
                            'Update FACEBOOK_PAGE_ACCESS_TOKEN environment variable',
                            'Verify webhook still works after update',
                            'Schedule next refresh for ~50 days from now'
                        ]
                    })
                    # Check more frequently when critical
                    results['next_check_recommended'] = datetime.now() + timedelta(hours=6)
                    
                elif days_until_expiry <= self.reminder_thresholds['warning']:
                    results['status'] = 'warning'
                    results['reminders'].append({
                        'priority': 'warning',
                        'message': f'Token expires in {days_until_expiry} days - plan refresh soon',
                        'expires_at': expires_at.isoformat(),
                        'recommended_actions': [
                            'Schedule time to refresh Facebook Page Access Token',
                            'Test the refresh process in a staging environment first',
                            'Ensure you have admin access to the Facebook Page',
                            'Document the refresh procedure for future reference'
                        ]
                    })
                    # Check daily when in warning period
                    results['next_check_recommended'] = datetime.now() + timedelta(hours=12)
                    
                elif days_until_expiry <= self.reminder_thresholds['notice']:
                    results['reminders'].append({
                        'priority': 'notice',
                        'message': f'Token expires in {days_until_expiry} days',
                        'expires_at': expires_at.isoformat(),
                        'note': 'Token refresh will be needed within a month'
                    })
            
            # Add token information to results
            results['token_info'] = {
                'page_name': token_info.get('page_name', 'Unknown'),
                'expires_at': expires_at.isoformat() if expires_at else 'Never/Long-lived',
                'type': token_info.get('token_type', 'Unknown'),
                'valid': token_info.get('token_valid', False)
            }
            
        except Exception as e:
            logger.error(f"Token refresh check failed: {str(e)}")
            results['status'] = 'error'
            results['actions_needed'].append({
                'priority': 'warning',
                'action': 'investigate_check_failure',
                'message': f'Token check failed: {str(e)}',
                'instructions': [
                    'Check network connectivity to Facebook Graph API',
                    'Verify FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are correct',
                    'Check application logs for detailed error information'
                ]
            })
        
        return results
    
    def get_refresh_instructions(self) -> list[str]:
        """Get step-by-step token refresh instructions"""
        return [
            "📋 Facebook Page Access Token Refresh Instructions:",
            "",
            "1. Go to Facebook Developer Console (developers.facebook.com)",
            "2. Select your app and navigate to 'App Roles' or 'Tools'",
            "3. Find 'Graph API Explorer' or 'Access Token Tool'",
            "4. Generate a new Page Access Token:",
            "   - Select your Facebook Page",
            "   - Choose required permissions (pages_messaging, pages_show_list)",
            "   - Generate token and copy it",
            "",
            "5. Update environment variable:",
            "   - Set FACEBOOK_PAGE_ACCESS_TOKEN to the new token",
            "   - Restart your application",
            "",
            "6. Verify the refresh:",
            "   - Check /health endpoint shows token as valid",
            "   - Send a test message to your webhook",
            "   - Monitor logs for any authentication errors",
            "",
            "⚠️  Important Notes:",
            "- Long-lived Page Access Tokens typically last ~60 days",
            "- Set a calendar reminder for ~50 days from now",
            "- Keep the old token until you verify the new one works",
            "- Test in staging environment first if possible",
            "",
            "📅 Recommended Schedule:",
            "- Check token status weekly via /ops endpoint",
            "- Refresh tokens every 50 days (before 60-day expiry)",
            "- Automate this process if you have multiple pages"
        ]

# Global reminder instance
token_refresh_reminder = TokenRefreshReminder()

def get_token_refresh_status() -> dict:
    """Get current token refresh status - convenience function"""
    return token_refresh_reminder.check_all_tokens()

def log_token_refresh_summary():
    """Log current token status to application logs"""
    try:
        status = token_refresh_reminder.check_all_tokens()
        
        if status['status'] == 'critical':
            logger.error(f"CRITICAL: Token refresh required immediately - {len(status['actions_needed'])} actions needed")
            for action in status['actions_needed']:
                logger.error(f"Action required: {action['message']}")
        elif status['status'] == 'warning':
            logger.warning(f"Token refresh needed soon - {len(status['reminders'])} reminders")
        elif status['status'] == 'healthy':
            logger.info("Token refresh status: healthy")
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to log token refresh summary: {str(e)}")
        return None