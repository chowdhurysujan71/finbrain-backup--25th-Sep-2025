"""
Data Integrity API endpoints
Provides monitoring and manual trigger capabilities for data integrity checks
"""

import logging
import os
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request

from utils.integrity_scheduler import integrity_scheduler
from utils.rate_limiting import limiter

logger = logging.getLogger(__name__)

integrity_api = Blueprint('integrity_api', __name__)

def require_admin(f):
    """Admin authentication decorator for integrity endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        admin_user = os.environ.get('ADMIN_USER')
        admin_pass = os.environ.get('ADMIN_PASS')
        
        if not auth or auth.username != admin_user or auth.password != admin_pass:
            return jsonify({"error": "Authentication required"}), 401
            
        return f(*args, **kwargs)
    return decorated_function

@integrity_api.route('/health/integrity', methods=['GET'])
@limiter.limit("60 per minute")
def integrity_health():
    """
    Health check endpoint for data integrity monitoring
    
    Returns:
        200: System healthy, recent checks passed
        503: System unhealthy, recent checks failed or system down
        
    Response format:
    {
        "status": "healthy|degraded|unhealthy",
        "last_check": "2024-09-19T02:00:00Z",
        "next_check": "2024-09-20T02:00:00Z", 
        "summary": "All checks passed",
        "checks_enabled": true,
        "scheduler_running": true
    }
    """
    try:
        status_info = integrity_scheduler.get_status()
        last_report = integrity_scheduler.get_last_report()
        
        # Determine overall health status
        if not status_info['checks_enabled'] or not status_info['scheduler_running']:
            health_status = 'unhealthy'
            http_status = 503
        elif last_report and last_report.overall_status == 'CRITICAL':
            health_status = 'unhealthy' 
            http_status = 503
        elif last_report and last_report.overall_status == 'WARNING':
            health_status = 'degraded'
            http_status = 200
        else:
            health_status = 'healthy'
            http_status = 200
        
        # Check if data is stale (no check in last 25 hours)
        if status_info['last_run_time']:
            last_run = datetime.fromisoformat(status_info['last_run_time'])
            hours_since_last_check = (datetime.utcnow() - last_run).total_seconds() / 3600
            if hours_since_last_check > 25:  # Daily check + 1 hour grace
                health_status = 'degraded'
                if http_status == 200:
                    http_status = 200  # Keep 200 but mark as degraded
        
        response = {
            'status': health_status,
            'last_check': status_info['last_run_time'],
            'next_check': status_info['next_scheduled_run'],
            'summary': status_info['last_report_summary'] or 'No checks run yet',
            'checks_enabled': status_info['checks_enabled'],
            'scheduler_running': status_info['scheduler_running'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(response), http_status
        
    except Exception as e:
        logger.error(f"Integrity health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': 'Health check system failure',
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@integrity_api.route('/integrity/status', methods=['GET'])
@require_admin
@limiter.limit("30 per minute")
def integrity_status():
    """
    Detailed status endpoint for operations team
    
    Returns comprehensive information about integrity check system
    """
    try:
        status_info = integrity_scheduler.get_status()
        last_report = integrity_scheduler.get_last_report()
        
        response = {
            'system': status_info,
            'last_report': last_report.to_dict() if last_report else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Integrity status check failed: {e}")
        return jsonify({
            'error': 'Status check failed',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@integrity_api.route('/integrity/run', methods=['POST'])
@require_admin
@limiter.limit("5 per minute")
def run_integrity_check():
    """
    Manual trigger for integrity checks
    
    Useful for:
    - On-demand validation after data fixes
    - Testing the integrity check system
    - Emergency validation during incidents
    
    Query parameters:
    - async: Run check asynchronously (default: false)
    """
    try:
        async_mode = request.args.get('async', 'false').lower() == 'true'
        
        if async_mode:
            # TODO: Implement async execution using background job queue
            return jsonify({
                'status': 'async_not_implemented',
                'message': 'Asynchronous execution not yet implemented',
                'timestamp': datetime.utcnow().isoformat()
            }), 501
        
        # Run synchronous check
        logger.info("Manual integrity check triggered")
        report = integrity_scheduler.run_manual_check()
        
        return jsonify({
            'status': 'completed',
            'report': report.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Manual integrity check failed: {e}")
        return jsonify({
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@integrity_api.route('/integrity/last-report', methods=['GET'])
@require_admin
@limiter.limit("30 per minute")
def get_last_report():
    """
    Get the last integrity check report
    
    Useful for:
    - Monitoring dashboards
    - Debugging data issues
    - Historical analysis
    """
    try:
        last_report = integrity_scheduler.get_last_report()
        
        if not last_report:
            return jsonify({
                'status': 'no_reports',
                'message': 'No integrity checks have been run yet',
                'timestamp': datetime.utcnow().isoformat()
            }), 404
        
        return jsonify({
            'report': last_report.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get last report: {e}")
        return jsonify({
            'error': 'Failed to retrieve report',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@integrity_api.route('/integrity/summary', methods=['GET'])
@require_admin
@limiter.limit("30 per minute")
def integrity_summary():
    """
    Quick summary endpoint for monitoring systems
    
    Returns minimal information for health checks and dashboards
    """
    try:
        last_report = integrity_scheduler.get_last_report()
        status_info = integrity_scheduler.get_status()
        
        if not last_report:
            summary = {
                'status': 'no_data',
                'message': 'No integrity checks run yet',
                'checks_enabled': status_info['checks_enabled'],
                'scheduler_running': status_info['scheduler_running']
            }
        else:
            summary = {
                'status': last_report.overall_status.lower(),
                'message': last_report.summary,
                'last_run': last_report.end_time,
                'total_checks': last_report.total_checks,
                'passed': last_report.passed,
                'failed': last_report.failed,
                'warnings': last_report.warnings,
                'checks_enabled': status_info['checks_enabled'],
                'scheduler_running': status_info['scheduler_running']
            }
        
        return jsonify(summary), 200
        
    except Exception as e:
        logger.error(f"Integrity summary failed: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500