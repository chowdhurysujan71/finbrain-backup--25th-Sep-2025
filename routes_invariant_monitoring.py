"""
🛡️ INVARIANT MONITORING ENDPOINTS
Real-time monitoring and health checks for single writer invariants
"""

import logging

from flask import Blueprint, jsonify

from utils.ci_invariant_enforcement import run_ci_invariant_check
from utils.unbreakable_invariants import (
    get_invariant_status,
    run_invariant_health_check,
)

logger = logging.getLogger(__name__)

# Create blueprint for invariant monitoring
invariant_monitoring_bp = Blueprint('invariant_monitoring', __name__)

@invariant_monitoring_bp.route('/ops/invariants/status', methods=['GET'])
def invariant_status():
    """
    🔍 GET CURRENT INVARIANT STATUS
    Returns real-time status of all single writer protections
    """
    try:
        status = get_invariant_status()
        return jsonify({
            'success': True,
            'data': status,
            'timestamp': status.get('last_check')
        })
    except Exception as e:
        logger.error(f"Failed to get invariant status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@invariant_monitoring_bp.route('/ops/invariants/health', methods=['GET'])
def invariant_health_check():
    """
    🏥 COMPREHENSIVE HEALTH CHECK
    Runs full health check of all invariant layers
    """
    try:
        health_result = run_invariant_health_check()
        
        # Determine HTTP status based on health
        status_code = 200
        if health_result.get('overall_status') == 'DEGRADED':
            status_code = 206  # Partial Content
        elif health_result.get('overall_status') in ['ERROR', 'FAIL']:
            status_code = 503  # Service Unavailable
            
        return jsonify({
            'success': True,
            'health': health_result
        }), status_code
        
    except Exception as e:
        logger.error(f"Invariant health check failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'health': {
                'overall_status': 'ERROR',
                'timestamp': None
            }
        }), 500

@invariant_monitoring_bp.route('/ops/invariants/ci-check', methods=['POST'])
def run_ci_check():
    """
    🔧 RUN CI INVARIANT CHECK
    Manually trigger CI-level invariant validation
    """
    try:
        # Run the CI check
        success = run_ci_invariant_check()
        
        return jsonify({
            'success': success,
            'message': 'CI invariant check completed',
            'status': 'PASS' if success else 'FAIL'
        }), 200 if success else 422
        
    except Exception as e:
        logger.error(f"CI invariant check failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'status': 'ERROR'
        }), 500

@invariant_monitoring_bp.route('/ops/invariants/test-enforcement', methods=['POST'])
def test_enforcement():
    """
    🧪 TEST INVARIANT ENFORCEMENT
    Safely test the invariant enforcement system
    """
    try:
        from utils.unbreakable_invariants import enforce_single_writer_invariant
        
        # Test data for validation
        test_cases = [
            {
                'name': 'valid_chat_source',
                'data': {
                    'source': 'chat',
                    'user_id': 'test_user',
                    'idempotency_key': 'test_key_123'
                },
                'should_pass': True
            },
            {
                'name': 'invalid_messenger_source',
                'data': {
                    'source': 'messenger',
                    'user_id': 'test_user',
                    'idempotency_key': 'test_key_456'
                },
                'should_pass': False
            },
            {
                'name': 'missing_source',
                'data': {
                    'user_id': 'test_user',
                    'idempotency_key': 'test_key_789'
                },
                'should_pass': False
            }
        ]
        
        results = []
        for test_case in test_cases:
            try:
                enforce_single_writer_invariant(test_case['data'])
                result = 'PASS'
                error = None
            except Exception as e:
                result = 'FAIL'
                error = str(e)
            
            # Check if result matches expectation
            expected_result = 'PASS' if test_case['should_pass'] else 'FAIL'
            test_passed = (result == expected_result)
            
            results.append({
                'test_name': test_case['name'],
                'result': result,
                'expected': expected_result,
                'test_passed': test_passed,
                'error': error
            })
        
        all_tests_passed = all(r['test_passed'] for r in results)
        
        return jsonify({
            'success': True,
            'all_tests_passed': all_tests_passed,
            'test_results': results
        })
        
    except Exception as e:
        logger.error(f"Enforcement test failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@invariant_monitoring_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Invariant monitoring endpoint not found'
    }), 404

@invariant_monitoring_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error in invariant monitoring'
    }), 500