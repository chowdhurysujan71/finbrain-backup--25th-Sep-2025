"""
Load Optimization and Performance Management for Coaching Flow
Caching, memory management, and performance monitoring
"""

import logging
import os
import time
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class CoachingCache:
    """
    Intelligent caching layer for coaching data
    Reduces database load and improves response times
    """
    
    def __init__(self):
        self.cache_enabled = os.getenv('COACH_CACHE_ENABLED', 'true').lower() == 'true'
        self.max_cache_size = int(os.getenv('COACH_CACHE_MAX_SIZE', '1000'))
        self.cache_ttl_seconds = int(os.getenv('COACH_CACHE_TTL_SEC', '300'))  # 5 minutes
        
        # LRU cache for topic suggestions and templates
        self.topic_cache = OrderedDict()
        self.template_cache = OrderedDict()
        self.user_context_cache = OrderedDict()
        
        # Performance tracking
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'last_cleanup': time.time()
        }
    
    def get_topic_suggestions(self, context_key: str) -> list[str] | None:
        """Get cached topic suggestions based on context"""
        if not self.cache_enabled:
            return None
        
        try:
            cache_entry = self.topic_cache.get(context_key)
            if cache_entry:
                # Check TTL
                if time.time() - cache_entry['timestamp'] < self.cache_ttl_seconds:
                    # Move to end (LRU)
                    self.topic_cache.move_to_end(context_key)
                    self.cache_stats['hits'] += 1
                    return cache_entry['suggestions']
                else:
                    # Expired
                    del self.topic_cache[context_key]
            
            self.cache_stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Topic cache error: {e}")
            return None
    
    def cache_topic_suggestions(self, context_key: str, suggestions: list[str]):
        """Cache topic suggestions"""
        if not self.cache_enabled:
            return
        
        try:
            # Cleanup if cache is full
            if len(self.topic_cache) >= self.max_cache_size:
                # Remove oldest entry
                self.topic_cache.popitem(last=False)
                self.cache_stats['evictions'] += 1
            
            self.topic_cache[context_key] = {
                'suggestions': suggestions.copy(),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Topic cache store error: {e}")
    
    def get_user_context(self, psid_hash: str) -> dict[str, Any] | None:
        """Get cached user context"""
        if not self.cache_enabled:
            return None
        
        try:
            cache_entry = self.user_context_cache.get(psid_hash)
            if cache_entry:
                if time.time() - cache_entry['timestamp'] < self.cache_ttl_seconds:
                    self.user_context_cache.move_to_end(psid_hash)
                    self.cache_stats['hits'] += 1
                    return cache_entry['context']
                else:
                    del self.user_context_cache[psid_hash]
            
            self.cache_stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"User context cache error: {e}")
            return None
    
    def cache_user_context(self, psid_hash: str, context: dict[str, Any]):
        """Cache user context"""
        if not self.cache_enabled:
            return
        
        try:
            if len(self.user_context_cache) >= self.max_cache_size:
                self.user_context_cache.popitem(last=False)
                self.cache_stats['evictions'] += 1
            
            self.user_context_cache[psid_hash] = {
                'context': context.copy(),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"User context cache store error: {e}")
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache performance statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'enabled': self.cache_enabled,
            'total_requests': total_requests,
            'hit_rate_pct': round(hit_rate, 1),
            'cache_sizes': {
                'topics': len(self.topic_cache),
                'templates': len(self.template_cache),
                'user_contexts': len(self.user_context_cache)
            },
            'evictions': self.cache_stats['evictions'],
            'max_size': self.max_cache_size,
            'ttl_seconds': self.cache_ttl_seconds
        }
    
    def cleanup_expired_entries(self):
        """Periodic cleanup of expired cache entries"""
        try:
            current_time = time.time()
            
            # Skip frequent cleanups
            if current_time - self.cache_stats['last_cleanup'] < 60:  # 1 minute
                return
            
            expired_count = 0
            
            # Clean topic cache
            expired_keys = [k for k, v in self.topic_cache.items() 
                           if current_time - v['timestamp'] > self.cache_ttl_seconds]
            for key in expired_keys:
                del self.topic_cache[key]
                expired_count += 1
            
            # Clean user context cache
            expired_keys = [k for k, v in self.user_context_cache.items() 
                           if current_time - v['timestamp'] > self.cache_ttl_seconds]
            for key in expired_keys:
                del self.user_context_cache[key]
                expired_count += 1
            
            self.cache_stats['last_cleanup'] = current_time
            
            if expired_count > 0:
                logger.debug(f"Cache cleanup: removed {expired_count} expired entries")
                
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")

class PerformanceMonitor:
    """
    Performance monitoring and optimization for coaching operations
    Tracks response times, memory usage, and system health
    """
    
    def __init__(self):
        self.monitoring_enabled = os.getenv('COACH_MONITORING_ENABLED', 'true').lower() == 'true'
        self.alert_threshold_ms = int(os.getenv('COACH_ALERT_THRESHOLD_MS', '1000'))
        self.memory_alert_threshold_mb = int(os.getenv('COACH_MEMORY_ALERT_THRESHOLD_MB', '100'))
        
        # Performance tracking
        self.operation_times = OrderedDict()  # Limited size for memory efficiency
        self.max_tracked_operations = 500
        
        # Memory tracking
        self.memory_samples = []
        self.max_memory_samples = 100
        
        # Alert tracking
        self.alerts_sent = {'performance': 0, 'memory': 0, 'errors': 0}
        self.last_alert_time = {'performance': 0, 'memory': 0, 'errors': 0}
        self.alert_cooldown_seconds = 300  # 5 minutes
    
    def track_operation(self, operation: str, duration_ms: float, success: bool = True):
        """Track operation performance"""
        if not self.monitoring_enabled:
            return
        
        try:
            # Store operation timing
            if len(self.operation_times) >= self.max_tracked_operations:
                self.operation_times.popitem(last=False)  # Remove oldest
            
            self.operation_times[time.time()] = {
                'operation': operation,
                'duration_ms': duration_ms,
                'success': success
            }
            
            # Check for performance alerts
            if duration_ms > self.alert_threshold_ms:
                self._send_performance_alert(operation, duration_ms)
            
            # Track with analytics if available
            try:
                from utils.coaching_analytics import coaching_analytics
                coaching_analytics.track_performance(operation, duration_ms, success)
            except ImportError:
                pass  # Analytics not available
            
        except Exception as e:
            logger.error(f"Performance tracking error: {e}")
    
    def track_memory_usage(self):
        """Track current memory usage"""
        if not self.monitoring_enabled:
            return
        
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            # Store memory sample
            if len(self.memory_samples) >= self.max_memory_samples:
                self.memory_samples.pop(0)  # Remove oldest
            
            self.memory_samples.append({
                'timestamp': time.time(),
                'memory_mb': memory_mb
            })
            
            # Check for memory alerts
            if memory_mb > self.memory_alert_threshold_mb:
                self._send_memory_alert(memory_mb)
                
        except ImportError:
            # psutil not available, skip memory tracking
            pass
        except Exception as e:
            logger.error(f"Memory tracking error: {e}")
    
    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance monitoring summary"""
        try:
            if not self.operation_times:
                return {'status': 'no_data', 'monitoring_enabled': self.monitoring_enabled}
            
            # Calculate statistics
            recent_operations = list(self.operation_times.values())[-100:]  # Last 100 ops
            durations = [op['duration_ms'] for op in recent_operations]
            
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            
            # Success rate
            successful_ops = sum(1 for op in recent_operations if op['success'])
            success_rate = successful_ops / len(recent_operations) * 100
            
            # Slow operations
            slow_ops = sum(1 for d in durations if d > self.alert_threshold_ms)
            slow_op_rate = slow_ops / len(durations) * 100
            
            # Memory statistics
            memory_stats = {}
            if self.memory_samples:
                recent_memory = [s['memory_mb'] for s in self.memory_samples[-20:]]
                memory_stats = {
                    'current_mb': recent_memory[-1] if recent_memory else 0,
                    'avg_mb': sum(recent_memory) / len(recent_memory),
                    'peak_mb': max(recent_memory),
                    'samples_count': len(self.memory_samples)
                }
            
            return {
                'monitoring_enabled': self.monitoring_enabled,
                'timestamp': datetime.utcnow().isoformat(),
                'performance': {
                    'operations_tracked': len(recent_operations),
                    'avg_duration_ms': round(avg_duration, 1),
                    'max_duration_ms': round(max_duration, 1),
                    'min_duration_ms': round(min_duration, 1),
                    'success_rate_pct': round(success_rate, 1),
                    'slow_operations_pct': round(slow_op_rate, 1)
                },
                'memory': memory_stats,
                'alerts': {
                    'performance_alerts': self.alerts_sent['performance'],
                    'memory_alerts': self.alerts_sent['memory'],
                    'error_alerts': self.alerts_sent['errors'],
                    'alert_threshold_ms': self.alert_threshold_ms
                },
                'health_status': self._get_performance_health_status(success_rate, slow_op_rate)
            }
            
        except Exception as e:
            logger.error(f"Performance summary error: {e}")
            return {'error': str(e), 'monitoring_enabled': self.monitoring_enabled}
    
    def _send_performance_alert(self, operation: str, duration_ms: float):
        """Send performance degradation alert"""
        try:
            current_time = time.time()
            
            # Check cooldown
            if current_time - self.last_alert_time['performance'] < self.alert_cooldown_seconds:
                return
            
            logger.warning(f"[PERFORMANCE ALERT] Slow operation: {operation} took {duration_ms:.0f}ms (threshold: {self.alert_threshold_ms}ms)")
            
            self.alerts_sent['performance'] += 1
            self.last_alert_time['performance'] = current_time
            
        except Exception as e:
            logger.error(f"Performance alert error: {e}")
    
    def _send_memory_alert(self, memory_mb: float):
        """Send memory usage alert"""
        try:
            current_time = time.time()
            
            if current_time - self.last_alert_time['memory'] < self.alert_cooldown_seconds:
                return
            
            logger.warning(f"[MEMORY ALERT] High memory usage: {memory_mb:.1f}MB (threshold: {self.memory_alert_threshold_mb}MB)")
            
            self.alerts_sent['memory'] += 1
            self.last_alert_time['memory'] = current_time
            
        except Exception as e:
            logger.error(f"Memory alert error: {e}")
    
    def _get_performance_health_status(self, success_rate: float, slow_op_rate: float) -> str:
        """Determine performance health status"""
        if success_rate < 90 or slow_op_rate > 20:  # <90% success or >20% slow ops
            return 'degraded'
        elif success_rate < 95 or slow_op_rate > 10:
            return 'warning'
        else:
            return 'healthy'

class MemoryOptimizer:
    """
    Memory management and optimization for coaching system
    Prevents memory leaks and manages resource cleanup
    """
    
    def __init__(self):
        self.cleanup_enabled = os.getenv('COACH_CLEANUP_ENABLED', 'true').lower() == 'true'
        self.cleanup_interval_seconds = int(os.getenv('COACH_CLEANUP_INTERVAL_SEC', '300'))  # 5 minutes
        self.last_cleanup = time.time()
        
        # Memory pressure detection
        self.memory_pressure_threshold = int(os.getenv('COACH_MEMORY_PRESSURE_THRESHOLD_MB', '200'))
        self.emergency_cleanup_threshold = int(os.getenv('COACH_EMERGENCY_CLEANUP_THRESHOLD_MB', '500'))
    
    def check_memory_pressure(self) -> tuple[bool, dict[str, Any]]:
        """Check if system is under memory pressure"""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            status = {
                'memory_mb': memory_mb,
                'pressure_threshold': self.memory_pressure_threshold,
                'emergency_threshold': self.emergency_cleanup_threshold,
                'under_pressure': memory_mb > self.memory_pressure_threshold,
                'emergency_level': memory_mb > self.emergency_cleanup_threshold
            }
            
            return status['under_pressure'] or status['emergency_level'], status
            
        except ImportError:
            # psutil not available
            return False, {'status': 'monitoring_unavailable'}
        except Exception as e:
            logger.error(f"Memory pressure check error: {e}")
            return False, {'error': str(e)}
    
    def perform_cleanup(self, emergency: bool = False) -> dict[str, Any]:
        """Perform memory cleanup operations"""
        if not self.cleanup_enabled:
            return {'status': 'cleanup_disabled'}
        
        try:
            cleanup_stats = {
                'start_time': time.time(),
                'emergency_mode': emergency,
                'items_cleaned': 0,
                'memory_freed_estimate': 0
            }
            
            # Cleanup expired cache entries
            try:
                from utils.coaching_optimization import coaching_cache
                coaching_cache.cleanup_expired_entries()
                cleanup_stats['items_cleaned'] += 10  # Estimate
            except (KeyError, AttributeError) as cache_error:
                logger.debug(f"Cache cleanup failed: {cache_error}")
                pass
            
            # Cleanup old session data if emergency
            if emergency:
                try:
                    self._emergency_session_cleanup()
                    cleanup_stats['items_cleaned'] += 50  # Estimate
                    cleanup_stats['memory_freed_estimate'] += 10  # MB estimate
                except Exception as e:
                    logger.error(f"Emergency session cleanup error: {e}")
            
            # Cleanup analytics data if under pressure
            if emergency:
                try:
                    from utils.coaching_analytics import coaching_analytics
                    # Limit metrics retention during emergency
                    for metric_list in coaching_analytics.metrics.values():
                        if hasattr(metric_list, 'maxlen'):
                            continue  # Already limited
                        while len(metric_list) > 100:  # Reduce to 100 items
                            metric_list.pop(0)
                            cleanup_stats['items_cleaned'] += 1
                except (IndexError, KeyError) as metric_error:
                    logger.debug(f"Metric cleanup failed: {metric_error}")
                    pass
            
            cleanup_stats['duration_ms'] = (time.time() - cleanup_stats['start_time']) * 1000
            self.last_cleanup = time.time()
            
            logger.info(f"Memory cleanup completed: {cleanup_stats['items_cleaned']} items cleaned")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Memory cleanup error: {e}")
            return {'error': str(e)}
    
    def _emergency_session_cleanup(self):
        """Emergency cleanup of old session data"""
        try:
            from utils.session import session_manager
            
            # If using memory store, clean very old entries
            if hasattr(session_manager, 'memory_store'):
                current_time = time.time()
                old_keys = []
                
                for key, data in session_manager.memory_store.items():
                    if isinstance(data, dict):
                        expires_at = data.get('expires_at', current_time)
                        # Clean entries that expired more than 1 hour ago
                        if expires_at < current_time - 3600:
                            old_keys.append(key)
                
                for key in old_keys:
                    del session_manager.memory_store[key]
                
                logger.info(f"Emergency cleanup: removed {len(old_keys)} old session entries")
                
        except Exception as e:
            logger.error(f"Emergency session cleanup error: {e}")

# Global optimization instances
coaching_cache = CoachingCache()
performance_monitor = PerformanceMonitor()
memory_optimizer = MemoryOptimizer()