"""
🚨 PRODUCTION MONITORING & SMOKE TEST ENDPOINTS
Real-time production health monitoring with auto-rollback recommendations
"""

from flask import Blueprint, jsonify, request
from utils.production_smoke_tests import run_production_smoke_test, get_smoke_test_history
import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Create blueprint for production monitoring
production_monitoring_bp = Blueprint('production_monitoring', __name__)

# Background smoke test scheduler
class SmokeTestScheduler:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_run = None
        self.interval_minutes = 15  # Run every 15 minutes
        self.last_results = None
        
    def start(self):
        """Start the background smoke test scheduler"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()
            logger.info("🚨 Production smoke test scheduler started")
    
    def stop(self):
        """Stop the background smoke test scheduler"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("🚨 Production smoke test scheduler stopped")
    
    def _run_scheduler(self):
        """Background scheduler thread"""
        while self.running:
            try:
                # Run smoke tests
                results = run_production_smoke_test()
                self.last_results = results
                self.last_run = datetime.now()
                
                # Log results
                status = results.get('overall_status', 'UNKNOWN')
                success_rate = results.get('success_rate', 0)
                logger.info(f"🚨 Scheduled smoke test completed: {status} ({success_rate:.1f}% success)")
                
                # Alert on failures
                if status in ['DEGRADED', 'CRITICAL']:
                    rollback_rec = results.get('rollback_recommendation', {})
                    if rollback_rec.get('recommended'):
                        logger.error(f"🚨 ROLLBACK RECOMMENDED: {rollback_rec.get('reason')}")
                        logger.error(f"🚨 Suggested action: {rollback_rec.get('suggested_action')}")
                
            except Exception as e:
                logger.error(f"Scheduled smoke test failed: {e}")
            
            # Wait for next interval
            time.sleep(self.interval_minutes * 60)

# Global scheduler instance
smoke_test_scheduler = SmokeTestScheduler()

@production_monitoring_bp.route('/ops/production/smoke-test', methods=['POST'])
def run_manual_smoke_test():
    """
    🔍 RUN MANUAL SMOKE TEST
    Manually trigger comprehensive production smoke tests
    """
    try:
        logger.info("🚨 Manual smoke test triggered")
        results = run_production_smoke_test()
        
        # Determine HTTP status based on results
        status_code = 200
        overall_status = results.get('overall_status', 'UNKNOWN')
        
        if overall_status == 'DEGRADED':
            status_code = 206  # Partial Content
        elif overall_status == 'CRITICAL':
            status_code = 503  # Service Unavailable
        
        return jsonify({
            'success': True,
            'smoke_test_results': results
        }), status_code
        
    except Exception as e:
        logger.error(f"Manual smoke test failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@production_monitoring_bp.route('/ops/production/status', methods=['GET'])
def get_production_status():
    """
    📊 GET PRODUCTION STATUS
    Returns current production health and recent smoke test results
    """
    try:
        # Get latest smoke test results
        latest_results = smoke_test_scheduler.last_results
        if not latest_results:
            # Run immediate smoke test if no recent results
            latest_results = run_production_smoke_test()
            smoke_test_scheduler.last_results = latest_results
            smoke_test_scheduler.last_run = datetime.now()
        
        # Build status response
        status_response = {
            'timestamp': datetime.now().isoformat(),
            'production_health': latest_results.get('overall_status', 'UNKNOWN'),
            'last_smoke_test': smoke_test_scheduler.last_run.isoformat() if smoke_test_scheduler.last_run else None,
            'success_rate': latest_results.get('success_rate', 0),
            'rollback_recommendation': latest_results.get('rollback_recommendation', {}),
            'scheduler_status': {
                'running': smoke_test_scheduler.running,
                'interval_minutes': smoke_test_scheduler.interval_minutes,
                'next_run_estimated': (smoke_test_scheduler.last_run + timedelta(minutes=smoke_test_scheduler.interval_minutes)).isoformat() if smoke_test_scheduler.last_run else None
            },
            'test_summary': {
                'total_tests': latest_results.get('total_tests', 0),
                'passed_tests': latest_results.get('passed_tests', 0),
                'failed_tests': latest_results.get('failed_tests', 0)
            }
        }
        
        # Determine HTTP status
        health_status = latest_results.get('overall_status', 'UNKNOWN')
        status_code = 200
        if health_status == 'DEGRADED':
            status_code = 206
        elif health_status in ['CRITICAL', 'UNKNOWN']:
            status_code = 503
        
        return jsonify({
            'success': True,
            'production_status': status_response
        }), status_code
        
    except Exception as e:
        logger.error(f"Production status check failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'production_status': {
                'production_health': 'ERROR',
                'timestamp': datetime.now().isoformat()
            }
        }), 500

@production_monitoring_bp.route('/ops/production/history', methods=['GET'])
def get_smoke_test_history_endpoint():
    """
    📈 GET SMOKE TEST HISTORY
    Returns recent smoke test execution history
    """
    try:
        history = get_smoke_test_history()
        
        return jsonify({
            'success': True,
            'smoke_test_history': history,
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"Smoke test history retrieval failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@production_monitoring_bp.route('/ops/production/scheduler', methods=['POST'])
def control_smoke_test_scheduler():
    """
    ⚙️ CONTROL SMOKE TEST SCHEDULER
    Start/stop the background smoke test scheduler
    """
    try:
        action = None
        if request.is_json and request.json:
            action = request.json.get('action')
        elif request.form:
            action = request.form.get('action')
        
        if action == 'start':
            if not smoke_test_scheduler.running:
                smoke_test_scheduler.start()
                message = "Smoke test scheduler started"
            else:
                message = "Smoke test scheduler already running"
                
        elif action == 'stop':
            if smoke_test_scheduler.running:
                smoke_test_scheduler.stop()
                message = "Smoke test scheduler stopped"
            else:
                message = "Smoke test scheduler already stopped"
                
        elif action == 'status':
            message = f"Scheduler status: {'running' if smoke_test_scheduler.running else 'stopped'}"
            
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid action. Use: start, stop, or status'
            }), 400
        
        return jsonify({
            'success': True,
            'message': message,
            'scheduler_running': smoke_test_scheduler.running,
            'last_run': smoke_test_scheduler.last_run.isoformat() if smoke_test_scheduler.last_run else None
        })
        
    except Exception as e:
        logger.error(f"Scheduler control failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@production_monitoring_bp.route('/ops/production/emergency-stop', methods=['POST'])
def emergency_stop():
    """
    🚨 EMERGENCY STOP
    Emergency endpoint to stop all production monitoring
    """
    try:
        smoke_test_scheduler.stop()
        
        logger.warning("🚨 EMERGENCY STOP ACTIVATED - Production monitoring halted")
        
        return jsonify({
            'success': True,
            'message': 'Emergency stop activated - all production monitoring halted',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Emergency stop failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Startup hook to begin automatic monitoring
def initialize_production_monitoring():
    """Initialize production monitoring on startup"""
    try:
        smoke_test_scheduler.start()
        logger.info("🚨 Production monitoring initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize production monitoring: {e}")

# Error handlers
@production_monitoring_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Production monitoring endpoint not found'
    }), 404

@production_monitoring_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error in production monitoring'
    }), 500