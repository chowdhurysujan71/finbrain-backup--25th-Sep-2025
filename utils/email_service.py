"""
Email service using Resend for transactional emails
Handles password reset emails and other transactional messages
"""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def get_resend_credentials() -> dict:
    """
    Get Resend API credentials from Replit connection
    Returns dict with api_key and from_email
    """
    try:
        hostname = os.environ.get('REPLIT_CONNECTORS_HOSTNAME')
        x_replit_token = None
        
        if os.environ.get('REPL_IDENTITY'):
            x_replit_token = 'repl ' + os.environ['REPL_IDENTITY']
        elif os.environ.get('WEB_REPL_RENEWAL'):
            x_replit_token = 'depl ' + os.environ['WEB_REPL_RENEWAL']
        
        if not x_replit_token or not hostname:
            raise Exception('Replit connection environment variables not found')
        
        response = requests.get(
            f'https://{hostname}/api/v2/connection?include_secrets=true&connector_names=resend',
            headers={
                'Accept': 'application/json',
                'X_REPLIT_TOKEN': x_replit_token
            },
            timeout=10
        )
        
        response.raise_for_status()
        data = response.json()
        
        connection_settings = data.get('items', [])[0] if data.get('items') else None
        
        if not connection_settings or not connection_settings.get('settings', {}).get('api_key'):
            raise Exception('Resend connection not properly configured')
        
        settings = connection_settings['settings']
        return {
            'api_key': settings['api_key'],
            'from_email': settings.get('from_email', 'noreply@finbrain.app')
        }
        
    except Exception as e:
        logger.error(f"Failed to get Resend credentials: {e}")
        raise


def send_password_reset_email(to_email: str, reset_token: str, user_name: Optional[str] = None) -> bool:
    """
    Send password reset email using Resend
    
    Args:
        to_email: Recipient email address
        reset_token: Password reset token (unhashed)
        user_name: Optional user name for personalization
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Get Resend credentials
        creds = get_resend_credentials()
        
        # Build reset link
        base_url = os.environ.get('REPLIT_DEV_DOMAIN', 'https://finbrain.app')
        if not base_url.startswith('http'):
            base_url = f'https://{base_url}'
        reset_link = f"{base_url}/auth/reset-password/{reset_token}"
        
        # Personalized greeting
        greeting = f"Hi {user_name}," if user_name else "Hi,"
        
        # Email content
        subject = "Reset your finbrain password"
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1976D2 0%, #1565C0 100%); padding: 32px 24px; border-radius: 8px 8px 0 0; text-align: center;">
            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 600;">finbrain</h1>
            <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">Your AI Financial Assistant</p>
        </div>
        
        <!-- Content -->
        <div style="padding: 32px 24px;">
            <p style="margin: 0 0 16px 0; font-size: 16px; color: #333333; line-height: 1.5;">{greeting}</p>
            
            <p style="margin: 0 0 24px 0; font-size: 16px; color: #333333; line-height: 1.5;">
                We received a request to reset your password. Click the button below to create a new password:
            </p>
            
            <!-- Reset Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="{reset_link}" style="display: inline-block; background-color: #1976D2; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 6px; font-size: 16px; font-weight: 600; box-shadow: 0 2px 4px rgba(25,118,210,0.3);">
                    Reset Password
                </a>
            </div>
            
            <!-- Security Info -->
            <div style="background-color: #FFF3CD; border-left: 4px solid #FFC107; padding: 16px; border-radius: 4px; margin: 24px 0;">
                <p style="margin: 0 0 8px 0; font-size: 14px; color: #856404; font-weight: 600;">
                    ⏰ Link expires in 1 hour
                </p>
                <p style="margin: 0; font-size: 13px; color: #856404; line-height: 1.5;">
                    For security, this reset link can only be used once. If you didn't request this, you can safely ignore this email.
                </p>
            </div>
            
            <!-- Alternative Link -->
            <p style="margin: 24px 0 0 0; font-size: 13px; color: #666666; line-height: 1.5;">
                If the button doesn't work, copy and paste this link into your browser:
            </p>
            <p style="margin: 8px 0 0 0; font-size: 13px; color: #1976D2; word-break: break-all; line-height: 1.5;">
                {reset_link}
            </p>
        </div>
        
        <!-- Footer -->
        <div style="background-color: #f8f9fa; padding: 24px; border-radius: 0 0 8px 8px; border-top: 1px solid #e9ecef;">
            <p style="margin: 0 0 8px 0; font-size: 13px; color: #666666; text-align: center;">
                This is an automated message from finbrain
            </p>
            <p style="margin: 0; font-size: 12px; color: #999999; text-align: center;">
                © 2025 finbrain. All rights reserved.
            </p>
        </div>
    </div>
</body>
</html>
"""
        
        # Plain text version
        text_body = f"""{greeting}

We received a request to reset your password.

Click this link to create a new password:
{reset_link}

⏰ This link expires in 1 hour and can only be used once.

If you didn't request this password reset, you can safely ignore this email.

---
finbrain - Your AI Financial Assistant
© 2025 finbrain. All rights reserved.
"""
        
        # Send email via Resend API
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f"Bearer {creds['api_key']}",
                'Content-Type': 'application/json'
            },
            json={
                'from': creds['from_email'],
                'to': [to_email],
                'subject': subject,
                'html': html_body,
                'text': text_body
            },
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"Password reset email sent successfully to {to_email} (ID: {result.get('id')})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        return False
