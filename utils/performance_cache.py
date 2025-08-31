"""
High-Performance Caching System for Report Generation
Implements intelligent caching with TTL and memory optimization
"""

import logging
import time
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Global cache storage with TTL support
_PERFORMANCE_CACHE = {}
_CACHE_STATS = {"hits": 0, "misses": 0, "evictions": 0}

class PerformanceCache:
    """Ultra-fast caching system for report generation"""
    
    def __init__(self, default_ttl_minutes: int = 5, max_size: int = 100):
        self.default_ttl_minutes = default_ttl_minutes
        self.max_size = max_size
        
    def _generate_cache_key(self, user_id: str, days_window: int, cache_type: str = "report") -> str:
        """Generate optimized cache key"""
        # Include current hour to ensure data freshness
        current_hour = datetime.now().strftime("%Y%m%d%H")
        key_data = f"{cache_type}:{user_id}:{days_window}:{current_hour}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]  # Short hash for speed
    
    def get_report(self, user_id: str, days_window: int) -> Optional[str]:
        """Get cached report if available and fresh"""
        try:
            cache_key = self._generate_cache_key(user_id, days_window, "report")
            
            if cache_key in _PERFORMANCE_CACHE:
                cached_item = _PERFORMANCE_CACHE[cache_key]
                
                # Check TTL
                if cached_item["expires_at"] > datetime.now():
                    _CACHE_STATS["hits"] += 1
                    logger.debug(f"Cache HIT for user {user_id[:8]}... (key: {cache_key})")
                    return cached_item["data"]
                else:
                    # Expired - remove
                    del _PERFORMANCE_CACHE[cache_key]
                    _CACHE_STATS["evictions"] += 1
            
            _CACHE_STATS["misses"] += 1
            logger.debug(f"Cache MISS for user {user_id[:8]}... (key: {cache_key})")
            return None
            
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    def set_report(self, user_id: str, days_window: int, report_data: str) -> bool:
        """Cache report with intelligent TTL"""
        try:
            cache_key = self._generate_cache_key(user_id, days_window, "report")
            
            # Clean cache if at max size
            if len(_PERFORMANCE_CACHE) >= self.max_size:
                self._cleanup_expired_entries()
                
                # If still at max, remove oldest entries
                if len(_PERFORMANCE_CACHE) >= self.max_size:
                    self._remove_oldest_entries(10)  # Remove 10% of entries
            
            # Store with TTL
            expires_at = datetime.now() + timedelta(minutes=self.default_ttl_minutes)
            _PERFORMANCE_CACHE[cache_key] = {
                "data": report_data,
                "created_at": datetime.now(),
                "expires_at": expires_at
            }
            
            logger.debug(f"Cached report for user {user_id[:8]}... (key: {cache_key}, TTL: {self.default_ttl_minutes}min)")
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def _cleanup_expired_entries(self):
        """Remove expired entries from cache"""
        now = datetime.now()
        expired_keys = [
            key for key, value in _PERFORMANCE_CACHE.items()
            if value["expires_at"] <= now
        ]
        
        for key in expired_keys:
            del _PERFORMANCE_CACHE[key]
            _CACHE_STATS["evictions"] += 1
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def _remove_oldest_entries(self, count: int):
        """Remove oldest entries when cache is full"""
        if not _PERFORMANCE_CACHE:
            return
            
        # Sort by creation time and remove oldest
        sorted_items = sorted(
            _PERFORMANCE_CACHE.items(),
            key=lambda x: x[1]["created_at"]
        )
        
        removal_count = min(count, len(sorted_items))
        for i in range(removal_count):
            key = sorted_items[i][0]
            del _PERFORMANCE_CACHE[key]
            _CACHE_STATS["evictions"] += 1
        
        logger.debug(f"Removed {removal_count} oldest cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = _CACHE_STATS["hits"] + _CACHE_STATS["misses"]
        hit_rate = (_CACHE_STATS["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache_size": len(_PERFORMANCE_CACHE),
            "hits": _CACHE_STATS["hits"],
            "misses": _CACHE_STATS["misses"],
            "evictions": _CACHE_STATS["evictions"],
            "hit_rate_percent": round(hit_rate, 1),
            "total_requests": total_requests
        }

# Global cache instance
performance_cache = PerformanceCache()