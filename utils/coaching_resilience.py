"""
Advanced Error Recovery for Coaching Flow
Handles session corruption, concurrent conflicts, and database failures
"""

import os
import time
import logging
import json
import hashlib
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CoachingResilience:
    """
    Advanced error recovery and conflict resolution for coaching sessions
    Purely defensive - never breaks existing functionality
    """
    
    def __init__(self):
        self.conflict_resolution_window = int(os.getenv('COACH_CONFLICT_WINDOW_SEC', '30'))
        self.corruption_detection_enabled = os.getenv('COACH_CORRUPTION_DETECTION', 'true').lower() == 'true'
        self.max_recovery_attempts = int(os.getenv('COACH_MAX_RECOVERY_ATTEMPTS', '3'))
        
    def validate_session_integrity(self, session_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate session data integrity without modifying anything
        Returns (is_valid, reason)
        """
        if not self.corruption_detection_enabled:
            return True, "validation_disabled"
        
        try:
            # Required fields check
            required_fields = ['state', 'turns', 'started_at']
            for field in required_fields:
                if field not in session_data:
                    return False, f"missing_field_{field}"
            
            # State validation
            valid_states = ['idle', 'await_focus', 'await_commit', 'cooldown']
            if session_data.get('state') not in valid_states:
                return False, f"invalid_state_{session_data.get('state')}"
            
            # Turns validation
            turns = session_data.get('turns', 0)
            if not isinstance(turns, int) or turns < 0 or turns > 10:  # Reasonable bounds
                return False, f"invalid_turns_{turns}"
            
            # Timestamp validation
            started_at = session_data.get('started_at', 0)
            if not isinstance(started_at, (int, float)) or started_at <= 0:
                return False, "invalid_timestamp"
            
            # Age validation (sessions older than 1 hour are suspicious)
            age_hours = (time.time() - started_at) / 3600
            if age_hours > 1:
                return False, f"session_too_old_{age_hours:.1f}h"
            
            return True, "valid"
            
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return False, f"validation_exception_{str(e)[:20]}"
    
    def detect_concurrent_conflict(self, psid_hash: str, session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detect if there's a concurrent session conflict
        Returns conflict info or None
        """
        try:
            from utils.session import get_coaching_session
            
            # Get current session from storage
            current_session = get_coaching_session(psid_hash)
            
            if not current_session:
                return None  # No conflict if no stored session
            
            # Check if sessions have different start times (indicating concurrent access)
            stored_start = current_session.get('started_at', 0)
            local_start = session_data.get('started_at', 0)
            
            time_diff = abs(stored_start - local_start)
            
            if time_diff > self.conflict_resolution_window:
                return {
                    'conflict_type': 'concurrent_sessions',
                    'stored_session_age': time.time() - stored_start,
                    'local_session_age': time.time() - local_start,
                    'time_difference': time_diff,
                    'resolution': 'keep_most_recent'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Concurrent conflict detection error: {e}")
            return {
                'conflict_type': 'detection_error',
                'error': str(e),
                'resolution': 'fail_safe'
            }
    
    def recover_corrupted_session(self, psid_hash: str, corruption_reason: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to recover a corrupted session safely
        Returns recovered session or None
        """
        try:
            logger.warning(f"Attempting session recovery for {psid_hash[:8]}... reason: {corruption_reason}")
            
            # Create minimal valid session based on corruption type
            current_time = time.time()
            
            if 'missing_field' in corruption_reason:
                # Reconstruct missing fields with safe defaults
                recovered_session = {
                    'state': 'idle',  # Safe default state
                    'turns': 0,
                    'started_at': current_time,
                    'recovery_applied': True,
                    'recovery_reason': corruption_reason,
                    'recovery_timestamp': current_time
                }
                
                logger.info(f"Session recovered with defaults for {psid_hash[:8]}...")
                return recovered_session
            
            elif 'invalid_state' in corruption_reason:
                # Reset to idle state
                recovered_session = {
                    'state': 'idle',
                    'turns': 0,
                    'started_at': current_time,
                    'recovery_applied': True,
                    'recovery_reason': corruption_reason
                }
                return recovered_session
            
            elif 'session_too_old' in corruption_reason:
                # Session expired, clear it
                from utils.session import delete_coaching_session
                delete_coaching_session(psid_hash)
                logger.info(f"Expired session cleaned up for {psid_hash[:8]}...")
                return None
            
            else:
                # Unknown corruption, fail safe
                logger.warning(f"Unknown corruption type: {corruption_reason}, clearing session")
                from utils.session import delete_coaching_session
                delete_coaching_session(psid_hash)
                return None
                
        except Exception as e:
            logger.error(f"Session recovery failed: {e}")
            return None
    
    def resolve_concurrent_conflict(self, psid_hash: str, conflict_info: Dict[str, Any]) -> bool:
        """
        Resolve concurrent session conflicts safely
        Returns True if resolved, False if failed
        """
        try:
            resolution = conflict_info.get('resolution', 'fail_safe')
            
            if resolution == 'keep_most_recent':
                # Keep the session with the most recent activity
                from utils.session import get_coaching_session, delete_coaching_session
                
                current_session = get_coaching_session(psid_hash)
                if not current_session:
                    return True  # Conflict auto-resolved
                
                # If stored session is very old, clear it
                stored_age = conflict_info.get('stored_session_age', 0)
                if stored_age > 3600:  # 1 hour
                    delete_coaching_session(psid_hash)
                    logger.info(f"Cleared old session for {psid_hash[:8]}... (age: {stored_age:.0f}s)")
                    return True
            
            elif resolution == 'fail_safe':
                # Clear the session to prevent further conflicts
                from utils.session import delete_coaching_session
                delete_coaching_session(psid_hash)
                logger.info(f"Fail-safe resolution: cleared session for {psid_hash[:8]}...")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Conflict resolution error: {e}")
            return False
    
    def safe_session_operation(self, psid_hash: str, operation_func, *args, **kwargs):
        """
        Execute session operation with automatic error recovery
        Wrapper that ensures operations never crash the system
        """
        attempt = 0
        while attempt < self.max_recovery_attempts:
            try:
                # Attempt the operation
                result = operation_func(*args, **kwargs)
                return result
                
            except Exception as e:
                attempt += 1
                logger.warning(f"Session operation failed (attempt {attempt}/{self.max_recovery_attempts}): {e}")
                
                if attempt >= self.max_recovery_attempts:
                    logger.error(f"Max recovery attempts reached for {psid_hash[:8]}...")
                    # Final fail-safe: clear the session
                    try:
                        from utils.session import delete_coaching_session
                        delete_coaching_session(psid_hash)
                    except:
                        pass  # Even clearing failed, but we don't crash
                    return None
                
                # Wait briefly before retry
                time.sleep(0.1 * attempt)
        
        return None

# Global resilience manager
coaching_resilience = CoachingResilience()