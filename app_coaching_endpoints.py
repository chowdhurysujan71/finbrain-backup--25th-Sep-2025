"""
Production monitoring and management endpoints for coaching system
Provides real-time metrics, health checks, and operational controls
"""

import os
import json
from datetime import datetime
from flask import Blueprint, jsonify, request

# Create coaching blueprint
coaching_bp = Blueprint('coaching', __name__, url_prefix='/ops/coaching')

# Import coaching components with fallback
try:
    from utils.coaching_analytics import coaching_analytics
    from utils.coaching_optimization import performance_monitor, coaching_cache, memory_optimizer
    from utils.coaching_safeguards import coaching_circuit_breaker, health_checker, feature_flag_manager
    from utils.coaching_resilience import coaching_resilience
    COACHING_MONITORING_AVAILABLE = True
except ImportError as e:
    COACHING_MONITORING_AVAILABLE = False
    import logging
    logging.getLogger(__name__).warning(f"Coaching monitoring not available: {e}")

@coaching_bp.route('/health', methods=['GET'])
def coaching_health():
    """Comprehensive coaching system health check"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({
                'status': 'monitoring_unavailable',
                'timestamp': datetime.utcnow().isoformat(),
                'message': 'Coaching monitoring components not loaded'
            }), 503
        
        # Perform full health check
        health_result = health_checker.perform_health_check()
        
        # Add circuit breaker status
        circuit_status = coaching_circuit_breaker.get_status()
        health_result['circuit_breaker'] = circuit_status
        
        # Determine HTTP status code based on health
        if health_result['overall_status'] == 'critical':
            status_code = 503
        elif health_result['overall_status'] == 'unhealthy':
            status_code = 503
        elif health_result['overall_status'] == 'degraded':
            status_code = 200  # Still operational
        else:
            status_code = 200
        
        return jsonify(health_result), status_code
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@coaching_bp.route('/metrics', methods=['GET'])
def coaching_metrics():
    """Real-time coaching metrics and analytics"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        # Get real-time metrics
        metrics = coaching_analytics.get_real_time_metrics()
        
        # Add performance metrics
        performance = performance_monitor.get_performance_summary()
        metrics['performance'] = performance
        
        # Add cache statistics
        cache_stats = coaching_cache.get_cache_stats()
        metrics['caching'] = cache_stats
        
        return jsonify(metrics)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@coaching_bp.route('/effectiveness', methods=['GET'])
def coaching_effectiveness():
    """Coaching effectiveness analysis and recommendations"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        report = coaching_analytics.get_coaching_effectiveness_report()
        return jsonify(report)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@coaching_bp.route('/circuit-breaker', methods=['GET'])
def circuit_breaker_status():
    """Circuit breaker status and controls"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        status = coaching_circuit_breaker.get_status()
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/circuit-breaker/open', methods=['POST'])
def force_circuit_open():
    """Manually open circuit breaker (emergency disable)"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Manual override')
        
        coaching_circuit_breaker.force_open(reason)
        
        return jsonify({
            'status': 'circuit_opened',
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/circuit-breaker/close', methods=['POST'])
def force_circuit_close():
    """Manually close circuit breaker (restore coaching)"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Manual restore')
        
        coaching_circuit_breaker.force_close(reason)
        
        return jsonify({
            'status': 'circuit_closed',
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/feature-flags', methods=['GET'])
def get_feature_flags():
    """Get current feature flag configuration"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        flags = feature_flag_manager.get_all_flags()
        return jsonify(flags)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/emergency-disable', methods=['POST'])
def emergency_disable():
    """Emergency disable all coaching features"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        data = request.get_json() or {}
        reason = data.get('reason', 'Emergency disable requested')
        
        # Force circuit breaker open
        coaching_circuit_breaker.force_open(f"Emergency: {reason}")
        
        # Disable feature flags
        feature_flag_manager.emergency_disable_all(reason)
        
        return jsonify({
            'status': 'emergency_disabled',
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat(),
            'actions': [
                'Circuit breaker opened',
                'All feature flags disabled',
                'Coaching system offline'
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/memory/status', methods=['GET'])
def memory_status():
    """Memory usage and optimization status"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        # Check memory pressure
        under_pressure, memory_status = memory_optimizer.check_memory_pressure()
        
        return jsonify({
            'memory_pressure': under_pressure,
            'memory_details': memory_status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/memory/cleanup', methods=['POST'])
def force_memory_cleanup():
    """Force memory cleanup operation"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        data = request.get_json() or {}
        emergency = data.get('emergency', False)
        
        cleanup_result = memory_optimizer.perform_cleanup(emergency=emergency)
        
        return jsonify({
            'cleanup_performed': True,
            'emergency_mode': emergency,
            'cleanup_stats': cleanup_result,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/cache/stats', methods=['GET'])
def cache_statistics():
    """Detailed cache performance statistics"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        stats = coaching_cache.get_cache_stats()
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear coaching caches"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        # Clear all caches
        coaching_cache.topic_cache.clear()
        coaching_cache.template_cache.clear()
        coaching_cache.user_context_cache.clear()
        
        return jsonify({
            'status': 'caches_cleared',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@coaching_bp.route('/dashboard', methods=['GET'])
def coaching_dashboard():
    """Comprehensive coaching system dashboard"""
    try:
        if not COACHING_MONITORING_AVAILABLE:
            return jsonify({'error': 'monitoring_unavailable'}), 503
        
        # Collect all dashboard data
        dashboard = {
            'timestamp': datetime.utcnow().isoformat(),
            'system_status': {
                'monitoring_available': COACHING_MONITORING_AVAILABLE,
                'overall_health': 'unknown'
            }
        }
        
        # Health status
        try:
            health_summary = health_checker.get_health_summary()
            dashboard['system_status']['overall_health'] = health_summary.get('current_status', 'unknown')
            dashboard['health'] = health_summary
        except Exception as e:
            dashboard['health'] = {'error': str(e)}
        
        # Real-time metrics
        try:
            metrics = coaching_analytics.get_real_time_metrics()
            dashboard['metrics'] = metrics
        except Exception as e:
            dashboard['metrics'] = {'error': str(e)}
        
        # Circuit breaker status
        try:
            circuit_status = coaching_circuit_breaker.get_status()
            dashboard['circuit_breaker'] = circuit_status
        except Exception as e:
            dashboard['circuit_breaker'] = {'error': str(e)}
        
        # Performance summary
        try:
            performance = performance_monitor.get_performance_summary()
            dashboard['performance'] = performance
        except Exception as e:
            dashboard['performance'] = {'error': str(e)}
        
        # Feature flags
        try:
            flags = feature_flag_manager.get_all_flags()
            dashboard['feature_flags'] = flags
        except Exception as e:
            dashboard['feature_flags'] = {'error': str(e)}
        
        return jsonify(dashboard)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500