"""
Lightweight session management for coaching flows
Supports Redis (preferred) with in-memory fallback and TTL cleanup
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Session manager with Redis primary, in-memory fallback
    Handles TTL, cleanup, and coaching state persistence
    """
    
    def __init__(self):
        self.redis_client = None
        self.memory_store = {}
        self.last_cleanup = time.time()
        
        # Try Redis connection
        try:
            import redis
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("Session manager initialized with Redis backend")
            else:
                logger.info("No REDIS_URL found, using in-memory session store")
        except Exception as e:
            logger.warning(f"Redis connection failed, using in-memory store: {e}")
            self.redis_client = None
    
    def _cleanup_memory_store(self):
        """Remove expired sessions from memory store"""
        if time.time() - self.last_cleanup < 60:  # Cleanup every minute
            return
            
        current_time = time.time()
        expired_keys = []
        
        for key, data in self.memory_store.items():
            if isinstance(data, dict) and data.get('expires_at', 0) < current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_store[key]
        
        self.last_cleanup = current_time
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired sessions")
    
    def get_session(self, key: str) -> Optional[Dict[str, Any]]:
        """Get session data by key"""
        try:
            if self.redis_client:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            else:
                self._cleanup_memory_store()
                data = self.memory_store.get(key)
                if data and data.get('expires_at', 0) > time.time():
                    return data
                elif data:
                    # Expired
                    del self.memory_store[key]
        except Exception as e:
            logger.error(f"Session get error for {key}: {e}")
        
        return None
    
    def set_session(self, key: str, data: Dict[str, Any], ttl_seconds: int = 300):
        """Set session data with TTL"""
        try:
            data['expires_at'] = time.time() + ttl_seconds
            
            if self.redis_client:
                self.redis_client.setex(key, ttl_seconds, json.dumps(data))
            else:
                self.memory_store[key] = data
                self._cleanup_memory_store()
                
        except Exception as e:
            logger.error(f"Session set error for {key}: {e}")
    
    def delete_session(self, key: str):
        """Delete session"""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self.memory_store.pop(key, None)
        except Exception as e:
            logger.error(f"Session delete error for {key}: {e}")
    
    def increment_daily_counter(self, psid_hash: str) -> int:
        """Increment and return daily coaching counter"""
        today = datetime.now().strftime('%Y-%m-%d')
        key = f"coach:count:{today}:{psid_hash}"
        
        try:
            if self.redis_client:
                count = self.redis_client.incr(key)
                self.redis_client.expire(key, 86400)  # 24 hours
                return count
            else:
                current_count = self.memory_store.get(key, {'count': 0, 'expires_at': time.time() + 86400})
                current_count['count'] += 1
                current_count['expires_at'] = time.time() + 86400
                self.memory_store[key] = current_count
                return current_count['count']
        except Exception as e:
            logger.error(f"Counter increment error for {key}: {e}")
            return 1  # Safe fallback
    
    def get_daily_counter(self, psid_hash: str) -> int:
        """Get daily coaching counter"""
        today = datetime.now().strftime('%Y-%m-%d')
        key = f"coach:count:{today}:{psid_hash}"
        
        try:
            if self.redis_client:
                count = self.redis_client.get(key)
                return int(count) if count else 0
            else:
                data = self.memory_store.get(key)
                if data and data.get('expires_at', 0) > time.time():
                    return data.get('count', 0)
                return 0
        except Exception as e:
            logger.error(f"Counter get error for {key}: {e}")
            return 0

# Global session manager instance
session_manager = SessionManager()

def get_coaching_session(psid_hash: str) -> Optional[Dict[str, Any]]:
    """Get coaching session for user"""
    key = f"coach:{psid_hash}"
    return session_manager.get_session(key)

def set_coaching_session(psid_hash: str, session_data: Dict[str, Any], ttl_seconds: int = 300):
    """Set coaching session for user"""
    key = f"coach:{psid_hash}"
    session_manager.set_session(key, session_data, ttl_seconds)

def delete_coaching_session(psid_hash: str):
    """Delete coaching session"""
    key = f"coach:{psid_hash}"
    session_manager.delete_session(key)

def increment_daily_coaching_count(psid_hash: str) -> int:
    """Increment daily coaching counter"""
    return session_manager.increment_daily_counter(psid_hash)

def get_daily_coaching_count(psid_hash: str) -> int:
    """Get daily coaching counter"""
    return session_manager.get_daily_counter(psid_hash)