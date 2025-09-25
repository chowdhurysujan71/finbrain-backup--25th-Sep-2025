"""
Secure Guest Token System
Generates and verifies HMAC-signed tokens for guest data linking
Prevents unauthorized access to guest expense data
"""
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Get server secret from environment, generate if missing
def get_token_secret() -> str:
    """Get or generate the secret for token signing"""
    secret = os.environ.get('GUEST_TOKEN_SECRET')
    if not secret:
        # Generate a secure random secret for development
        secret = secrets.token_urlsafe(32)
        logger.warning("Using generated GUEST_TOKEN_SECRET for development. Set environment variable for production.")
        os.environ['GUEST_TOKEN_SECRET'] = secret
    return secret

def generate_guest_token(guest_id: str, validity_hours: int = 720) -> str:
    """
    Generate a secure HMAC-signed token for guest data linking
    
    Args:
        guest_id: The guest user identifier
        validity_hours: Token validity in hours (default: 30 days)
        
    Returns:
        Base64-encoded signed token containing guest_id, timestamp, and signature
    """
    try:
        # Create token payload
        expiry_timestamp = int(time.time()) + (validity_hours * 3600)
        nonce = secrets.token_urlsafe(8)  # Prevent replay attacks
        
        payload = {
            'guest_id': guest_id,
            'expires': expiry_timestamp,
            'nonce': nonce,
            'version': '1.0'
        }
        
        # Convert to JSON and encode
        payload_json = json.dumps(payload, sort_keys=True)
        payload_bytes = payload_json.encode('utf-8')
        
        # Generate HMAC signature
        secret = get_token_secret().encode('utf-8')
        signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
        
        # Create final token
        token_data = {
            'payload': payload_json,
            'signature': signature
        }
        
        # Base64 encode the complete token
        token_json = json.dumps(token_data)
        token_bytes = token_json.encode('utf-8')
        import base64
        token = base64.urlsafe_b64encode(token_bytes).decode('utf-8')
        
        logger.info(f"Generated secure guest token for guest {guest_id[:8]}*** (expires: {expiry_timestamp})")
        
        return token
        
    except Exception as e:
        logger.error(f"Failed to generate guest token: {e}")
        raise ValueError("Token generation failed")

def verify_guest_token(token: str, expected_guest_id: str) -> tuple[bool, dict[str, Any] | None]:
    """
    Verify a guest token and return validation result
    
    Args:
        token: The token to verify
        expected_guest_id: The guest ID we expect this token to be for
        
    Returns:
        Tuple of (is_valid, payload_data_or_error_info)
    """
    try:
        if not token or not expected_guest_id:
            return False, {"error": "Token and guest ID required"}
        
        # Decode base64 token
        import base64
        try:
            token_bytes = base64.urlsafe_b64decode(token.encode('utf-8'))
            token_json = token_bytes.decode('utf-8')
            token_data = json.loads(token_json)
        except Exception as e:
            logger.warning(f"Invalid token format: {e}")
            return False, {"error": "Invalid token format"}
        
        # Extract payload and signature
        payload_json = token_data.get('payload')
        provided_signature = token_data.get('signature')
        
        if not payload_json or not provided_signature:
            return False, {"error": "Malformed token structure"}
        
        # Verify signature
        secret = get_token_secret().encode('utf-8')
        payload_bytes = payload_json.encode('utf-8')
        expected_signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(provided_signature, expected_signature):
            logger.warning(f"Token signature verification failed for guest {expected_guest_id[:8]}***")
            return False, {"error": "Invalid token signature"}
        
        # Parse payload
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            return False, {"error": "Invalid payload format"}
        
        # Verify guest ID matches
        token_guest_id = payload.get('guest_id')
        if token_guest_id != expected_guest_id:
            logger.warning(f"Token guest ID mismatch: token={token_guest_id[:8]}***, expected={expected_guest_id[:8]}***")
            return False, {"error": "Token guest ID mismatch"}
        
        # Check expiry
        expires = payload.get('expires')
        if not expires or time.time() > expires:
            logger.info(f"Token expired for guest {expected_guest_id[:8]}***")
            return False, {"error": "Token expired"}
        
        # All checks passed
        logger.info(f"Token verification successful for guest {expected_guest_id[:8]}***")
        return True, payload
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return False, {"error": "Token verification failed"}

def is_token_recently_used(guest_id: str, nonce: str) -> bool:
    """
    Check if a token nonce has been recently used (basic replay protection)
    In production, this should use Redis or similar for distributed storage
    
    Args:
        guest_id: Guest identifier
        nonce: Token nonce to check
        
    Returns:
        True if token was recently used
    """
    try:
        # For now, use simple in-memory tracking
        # In production, implement with Redis with expiry
        used_tokens_key = "used_guest_tokens"
        
        # Simple implementation - in production use proper cache
        import tempfile
        cache_file = os.path.join(tempfile.gettempdir(), f"finbrain_token_cache_{guest_id}.txt")
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    used_nonces = f.read().split('\n')
                if nonce in used_nonces:
                    return True
            except Exception:
                pass  # Cache read error, continue
        
        return False
        
    except Exception as e:
        logger.error(f"Token usage check error: {e}")
        return False  # Err on the side of allowing access

def mark_token_as_used(guest_id: str, nonce: str):
    """
    Mark a token nonce as used to prevent replay attacks
    
    Args:
        guest_id: Guest identifier
        nonce: Token nonce to mark as used
    """
    try:
        import tempfile
        cache_file = os.path.join(tempfile.gettempdir(), f"finbrain_token_cache_{guest_id}.txt")
        
        # Read existing nonces
        used_nonces = []
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    used_nonces = [line.strip() for line in f.readlines() if line.strip()]
            except Exception:
                pass
        
        # Add new nonce
        used_nonces.append(nonce)
        
        # Keep only recent nonces (last 100)
        used_nonces = used_nonces[-100:]
        
        # Write back
        with open(cache_file, 'w') as f:
            f.write('\n'.join(used_nonces))
            
        logger.debug(f"Marked token nonce as used for guest {guest_id[:8]}***")
        
    except Exception as e:
        logger.error(f"Failed to mark token as used: {e}")
        # Don't fail the operation if we can't mark it as used

def cleanup_expired_tokens():
    """
    Clean up expired token tracking data
    Should be called periodically in production
    """
    try:
        import glob
        import tempfile
        
        cache_pattern = os.path.join(tempfile.gettempdir(), "finbrain_token_cache_*.txt")
        cache_files = glob.glob(cache_pattern)
        
        # Remove cache files older than 30 days
        current_time = time.time()
        for cache_file in cache_files:
            try:
                file_age = current_time - os.path.getmtime(cache_file)
                if file_age > (30 * 24 * 3600):  # 30 days
                    os.remove(cache_file)
                    logger.debug(f"Cleaned up expired token cache: {cache_file}")
            except Exception:
                continue  # Skip problematic files
                
    except Exception as e:
        logger.error(f"Token cleanup error: {e}")