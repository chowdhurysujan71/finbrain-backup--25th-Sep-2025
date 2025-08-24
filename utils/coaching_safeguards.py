"""
Advanced Deployment Safeguards for Coaching Flow
Circuit breakers, health checks, and rollback mechanisms
"""

import os
import time
import logging
import json
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class SystemHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"

class CoachingCircuitBreaker:
    """
    Circuit breaker for coaching system
    Automatically disables coaching when system health degrades
    """
    
    def __init__(self):
        self.enabled = os.getenv('COACH_CIRCUIT_BREAKER_ENABLED', 'true').lower() == 'true'
        self.failure_threshold = int(os.getenv('COACH_FAILURE_THRESHOLD', '5'))
        self.success_threshold = int(os.getenv('COACH_SUCCESS_THRESHOLD', '3'))
        self.timeout_seconds = int(os.getenv('COACH_CIRCUIT_TIMEOUT_SEC', '60'))
        
        # Circuit breaker state
        self.state = 'closed'  # closed, open, half-open
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.state_changed_time = time.time()
        
        # Health tracking
        self.health_checks = []
        self.last_health_check = time.time()
    
    def call(self, operation: Callable, *args, **kwargs):
        """Execute operation through circuit breaker"""
        if not self.enabled:
            return operation(*args, **kwargs)
        
        current_time = time.time()
        
        # Check if we should transition from open to half-open
        if self.state == 'open':
            if current_time - self.last_failure_time > self.timeout_seconds:
                self.state = 'half-open'
                self.success_count = 0
                logger.info("[CIRCUIT] Transitioning to half-open state")
        
        # If circuit is open, fail fast
        if self.state == 'open':
            raise Exception("Circuit breaker is OPEN - coaching temporarily disabled")
        
        try:
            # Execute the operation
            result = operation(*args, **kwargs)
            
            # Operation succeeded
            self._record_success()
            return result
            
        except Exception as e:
            # Operation failed
            self._record_failure(str(e))
            raise
    
    def _record_success(self):
        """Record successful operation"""
        if self.state == 'half-open':
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = 'closed'
                self.failure_count = 0
                self.state_changed_time = time.time()
                logger.info("[CIRCUIT] Circuit breaker CLOSED - coaching restored")
        elif self.state == 'closed':
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)
    
    def _record_failure(self, error: str):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == 'closed' and self.failure_count >= self.failure_threshold:
            self.state = 'open'
            self.state_changed_time = time.time()
            logger.error(f"[CIRCUIT] Circuit breaker OPENED - coaching disabled due to failures: {error}")
        elif self.state == 'half-open':
            self.state = 'open'
            self.state_changed_time = time.time()
            logger.error(f"[CIRCUIT] Circuit breaker reopened - coaching disabled: {error}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            'enabled': self.enabled,
            'state': self.state,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.failure_threshold,
            'success_threshold': self.success_threshold,
            'timeout_seconds': self.timeout_seconds,
            'last_failure_time': self.last_failure_time,
            'state_changed_time': self.state_changed_time,
            'coaching_available': self.state != 'open'
        }
    
    def force_open(self, reason: str):
        """Manually open circuit breaker"""
        self.state = 'open'
        self.state_changed_time = time.time()
        self.last_failure_time = time.time()
        logger.warning(f"[CIRCUIT] Circuit breaker manually OPENED: {reason}")
    
    def force_close(self, reason: str):
        """Manually close circuit breaker"""
        self.state = 'closed'
        self.failure_count = 0
        self.success_count = 0
        self.state_changed_time = time.time()
        logger.info(f"[CIRCUIT] Circuit breaker manually CLOSED: {reason}")

class HealthChecker:
    """
    Comprehensive health checking for coaching system
    Monitors various system components and overall health
    """
    
    def __init__(self):
        self.enabled = os.getenv('COACH_HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
        self.check_interval_seconds = int(os.getenv('COACH_HEALTH_CHECK_INTERVAL_SEC', '60'))
        
        # Health thresholds
        self.response_time_threshold_ms = int(os.getenv('COACH_HEALTH_RESPONSE_THRESHOLD_MS', '1000'))
        self.error_rate_threshold = float(os.getenv('COACH_HEALTH_ERROR_RATE_THRESHOLD', '5.0'))
        self.memory_threshold_mb = int(os.getenv('COACH_HEALTH_MEMORY_THRESHOLD_MB', '200'))
        
        # Health history
        self.health_history = []
        self.max_history_size = 100
        self.last_check_time = 0
    
    def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        if not self.enabled:
            return {'status': 'disabled', 'timestamp': datetime.utcnow().isoformat()}
        
        current_time = time.time()
        health_result = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': SystemHealth.HEALTHY.value,
            'components': {},
            'metrics': {},
            'alerts': []
        }
        
        try:
            # Check session management health
            session_health = self._check_session_health()
            health_result['components']['session_management'] = session_health
            
            # Check analytics health
            analytics_health = self._check_analytics_health()
            health_result['components']['analytics'] = analytics_health
            
            # Check performance health
            performance_health = self._check_performance_health()
            health_result['components']['performance'] = performance_health
            
            # Check memory health
            memory_health = self._check_memory_health()
            health_result['components']['memory'] = memory_health
            
            # Check circuit breaker status
            circuit_health = self._check_circuit_breaker_health()
            health_result['components']['circuit_breaker'] = circuit_health
            
            # Determine overall health
            health_result['overall_status'] = self._calculate_overall_health(health_result['components'])
            
            # Generate alerts based on health status
            health_result['alerts'] = self._generate_health_alerts(health_result)
            
            # Store in history
            if len(self.health_history) >= self.max_history_size:
                self.health_history.pop(0)
            self.health_history.append(health_result)
            
            self.last_check_time = current_time
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            health_result['overall_status'] = SystemHealth.CRITICAL.value
            health_result['error'] = str(e)
        
        return health_result
    
    def _check_session_health(self) -> Dict[str, Any]:
        """Check session management component health"""
        try:
            start_time = time.time()
            
            # Test session operations
            test_psid = "health_check_test"
            from utils.session import get_coaching_session, set_coaching_session, delete_coaching_session
            
            # Test write
            test_session = {'state': 'test', 'health_check': True, 'timestamp': time.time()}
            set_coaching_session(test_psid, test_session, 60)
            
            # Test read
            retrieved = get_coaching_session(test_psid)
            
            # Test delete
            delete_coaching_session(test_psid)
            
            response_time = (time.time() - start_time) * 1000
            
            if retrieved and retrieved.get('health_check'):
                return {
                    'status': SystemHealth.HEALTHY.value,
                    'response_time_ms': round(response_time, 1),
                    'operations_successful': True
                }
            else:
                return {
                    'status': SystemHealth.DEGRADED.value,
                    'response_time_ms': round(response_time, 1),
                    'operations_successful': False,
                    'issue': 'session_read_failed'
                }
                
        except Exception as e:
            return {
                'status': SystemHealth.UNHEALTHY.value,
                'error': str(e),
                'operations_successful': False
            }
    
    def _check_analytics_health(self) -> Dict[str, Any]:
        """Check analytics component health"""
        try:
            from utils.coaching_analytics import coaching_analytics
            
            # Test analytics operations
            start_time = time.time()
            metrics = coaching_analytics.get_real_time_metrics()
            response_time = (time.time() - start_time) * 1000
            
            if metrics and 'error' not in metrics:
                return {
                    'status': SystemHealth.HEALTHY.value,
                    'response_time_ms': round(response_time, 1),
                    'metrics_available': True,
                    'total_sessions': metrics.get('session_metrics', {}).get('started_24h', 0)
                }
            else:
                return {
                    'status': SystemHealth.DEGRADED.value,
                    'response_time_ms': round(response_time, 1),
                    'metrics_available': False,
                    'issue': 'metrics_generation_failed'
                }
                
        except Exception as e:
            return {
                'status': SystemHealth.UNHEALTHY.value,
                'error': str(e),
                'metrics_available': False
            }
    
    def _check_performance_health(self) -> Dict[str, Any]:
        """Check performance component health"""
        try:
            from utils.coaching_optimization import performance_monitor
            
            summary = performance_monitor.get_performance_summary()
            
            if 'error' in summary:
                return {
                    'status': SystemHealth.UNHEALTHY.value,
                    'error': summary['error']
                }
            
            # Check performance metrics
            perf_metrics = summary.get('performance', {})
            avg_duration = perf_metrics.get('avg_duration_ms', 0)
            success_rate = perf_metrics.get('success_rate_pct', 100)
            
            if avg_duration > self.response_time_threshold_ms or success_rate < 95:
                status = SystemHealth.DEGRADED.value
            else:
                status = SystemHealth.HEALTHY.value
            
            return {
                'status': status,
                'avg_response_time_ms': avg_duration,
                'success_rate_pct': success_rate,
                'monitoring_active': summary.get('monitoring_enabled', False)
            }
            
        except Exception as e:
            return {
                'status': SystemHealth.UNHEALTHY.value,
                'error': str(e)
            }
    
    def _check_memory_health(self) -> Dict[str, Any]:
        """Check memory usage health"""
        try:
            from utils.coaching_optimization import memory_optimizer
            
            under_pressure, memory_status = memory_optimizer.check_memory_pressure()
            
            if 'error' in memory_status:
                return {
                    'status': SystemHealth.DEGRADED.value,
                    'monitoring_available': False,
                    'error': memory_status['error']
                }
            
            if 'monitoring_unavailable' in memory_status.values():
                return {
                    'status': SystemHealth.HEALTHY.value,
                    'monitoring_available': False,
                    'note': 'memory_monitoring_disabled'
                }
            
            memory_mb = memory_status.get('memory_mb', 0)
            
            if memory_status.get('emergency_level'):
                status = SystemHealth.CRITICAL.value
            elif memory_status.get('under_pressure'):
                status = SystemHealth.DEGRADED.value
            else:
                status = SystemHealth.HEALTHY.value
            
            return {
                'status': status,
                'memory_mb': round(memory_mb, 1),
                'pressure_threshold_mb': memory_status.get('pressure_threshold'),
                'under_pressure': under_pressure,
                'monitoring_available': True
            }
            
        except Exception as e:
            return {
                'status': SystemHealth.UNHEALTHY.value,
                'error': str(e)
            }
    
    def _check_circuit_breaker_health(self) -> Dict[str, Any]:
        """Check circuit breaker status"""
        try:
            from utils.coaching_safeguards import coaching_circuit_breaker
            
            status = coaching_circuit_breaker.get_status()
            
            if status['state'] == 'open':
                health_status = SystemHealth.CRITICAL.value
            elif status['state'] == 'half-open':
                health_status = SystemHealth.DEGRADED.value
            else:
                health_status = SystemHealth.HEALTHY.value
            
            return {
                'status': health_status,
                'circuit_state': status['state'],
                'coaching_available': status['coaching_available'],
                'failure_count': status['failure_count']
            }
            
        except Exception as e:
            return {
                'status': SystemHealth.UNHEALTHY.value,
                'error': str(e)
            }
    
    def _calculate_overall_health(self, components: Dict[str, Dict]) -> str:
        """Calculate overall health from component health"""
        health_scores = []
        
        for component, health in components.items():
            status = health.get('status', SystemHealth.HEALTHY.value)
            if status == SystemHealth.CRITICAL.value:
                health_scores.append(0)
            elif status == SystemHealth.UNHEALTHY.value:
                health_scores.append(1)
            elif status == SystemHealth.DEGRADED.value:
                health_scores.append(2)
            else:  # HEALTHY
                health_scores.append(3)
        
        if not health_scores:
            return SystemHealth.HEALTHY.value
        
        avg_score = sum(health_scores) / len(health_scores)
        
        if avg_score < 1:
            return SystemHealth.CRITICAL.value
        elif avg_score < 1.5:
            return SystemHealth.UNHEALTHY.value
        elif avg_score < 2.5:
            return SystemHealth.DEGRADED.value
        else:
            return SystemHealth.HEALTHY.value
    
    def _generate_health_alerts(self, health_result: Dict) -> List[str]:
        """Generate alerts based on health status"""
        alerts = []
        
        overall_status = health_result.get('overall_status')
        if overall_status == SystemHealth.CRITICAL.value:
            alerts.append("CRITICAL: Coaching system health is critical - immediate attention required")
        elif overall_status == SystemHealth.UNHEALTHY.value:
            alerts.append("WARNING: Coaching system health is unhealthy - investigation needed")
        elif overall_status == SystemHealth.DEGRADED.value:
            alerts.append("NOTICE: Coaching system performance is degraded")
        
        # Component-specific alerts
        components = health_result.get('components', {})
        for component, health in components.items():
            if health.get('status') == SystemHealth.CRITICAL.value:
                alerts.append(f"CRITICAL: {component} component is in critical state")
            elif health.get('status') == SystemHealth.UNHEALTHY.value:
                alerts.append(f"WARNING: {component} component is unhealthy")
        
        return alerts
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get current health summary"""
        if not self.health_history:
            return {'status': 'no_data', 'last_check': 'never'}
        
        latest_health = self.health_history[-1]
        
        return {
            'current_status': latest_health['overall_status'],
            'last_check': latest_health['timestamp'],
            'check_interval_seconds': self.check_interval_seconds,
            'components_count': len(latest_health.get('components', {})),
            'active_alerts': len(latest_health.get('alerts', [])),
            'health_history_size': len(self.health_history)
        }

class FeatureFlagManager:
    """
    Advanced feature flag management for gradual rollouts and emergency rollbacks
    """
    
    def __init__(self):
        self.enabled = os.getenv('COACH_FEATURE_FLAGS_ENABLED', 'true').lower() == 'true'
        
        # Feature flags with granular control
        self.flags = {
            'coaching_enabled': os.getenv('COACH_ENABLED', 'true').lower() == 'true',
            'coaching_analytics': os.getenv('COACH_ANALYTICS_ENABLED', 'true').lower() == 'true',
            'coaching_caching': os.getenv('COACH_CACHE_ENABLED', 'true').lower() == 'true',
            'coaching_monitoring': os.getenv('COACH_MONITORING_ENABLED', 'true').lower() == 'true',
            'coaching_circuit_breaker': os.getenv('COACH_CIRCUIT_BREAKER_ENABLED', 'true').lower() == 'true'
        }
        
        # Rollout percentages for gradual deployment
        self.rollout_percentages = {
            'coaching_beta_users': int(os.getenv('COACH_BETA_ROLLOUT_PCT', '100')),
            'coaching_analytics': int(os.getenv('COACH_ANALYTICS_ROLLOUT_PCT', '100')),
            'coaching_optimization': int(os.getenv('COACH_OPTIMIZATION_ROLLOUT_PCT', '100'))
        }
    
    def is_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """Check if feature flag is enabled for user"""
        if not self.enabled:
            return True  # Default to enabled if flag system is disabled
        
        # Check basic flag
        if not self.flags.get(flag_name, False):
            return False
        
        # Check rollout percentage if user provided
        if user_id and flag_name in self.rollout_percentages:
            rollout_pct = self.rollout_percentages[flag_name]
            if rollout_pct < 100:
                # Simple hash-based rollout
                import hashlib
                user_hash = hashlib.md5(user_id.encode()).hexdigest()
                user_bucket = int(user_hash[:2], 16) % 100  # 0-99
                return user_bucket < rollout_pct
        
        return True
    
    def get_all_flags(self) -> Dict[str, Any]:
        """Get all feature flags and rollout settings"""
        return {
            'enabled': self.enabled,
            'flags': self.flags.copy(),
            'rollout_percentages': self.rollout_percentages.copy(),
            'last_updated': datetime.utcnow().isoformat()
        }
    
    def emergency_disable_all(self, reason: str):
        """Emergency disable all coaching features"""
        logger.critical(f"EMERGENCY DISABLE: All coaching features disabled - {reason}")
        
        for flag in self.flags:
            self.flags[flag] = False
        
        # Also disable circuit breaker to force fail-fast
        try:
            from utils.coaching_safeguards import coaching_circuit_breaker
            coaching_circuit_breaker.force_open(f"Emergency disable: {reason}")
        except:
            pass

# Global safeguard instances
coaching_circuit_breaker = CoachingCircuitBreaker()
health_checker = HealthChecker()
feature_flag_manager = FeatureFlagManager()