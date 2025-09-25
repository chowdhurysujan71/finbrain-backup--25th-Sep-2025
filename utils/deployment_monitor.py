"""
Platform-Wide Deployment Monitor
Ensures Messenger delivery fixes are working for all users
"""

import logging
import time
from datetime import datetime
from typing import Dict, List

from sqlalchemy import text

from db_base import db

logger = logging.getLogger(__name__)

class DeploymentMonitor:
    """Monitor platform-wide deployment health for Messenger delivery"""
    
    def __init__(self):
        self.success_threshold = 95.0  # Minimum success rate
        self.sample_size = 10  # Users to test per check
        
    def check_platform_health(self) -> dict:
        """Comprehensive platform health check"""
        try:
            # Get platform statistics
            stats = self._get_platform_stats()
            
            # Test sample of users
            user_test_results = self._test_sample_users()
            
            # Test new user compatibility
            new_user_results = self._test_new_user_compatibility()
            
            # Check for deployment issues
            issues = self._detect_issues(user_test_results, new_user_results)
            
            # Generate report
            report = {
                'timestamp': datetime.utcnow().isoformat(),
                'platform_stats': stats,
                'existing_users': user_test_results,
                'new_user_compatibility': new_user_results,
                'issues_detected': issues,
                'overall_status': 'HEALTHY' if not issues else 'DEGRADED',
                'action_required': len(issues) > 0
            }
            
            # Log results
            if issues:
                logger.warning(f"Platform health issues detected: {len(issues)} problems")
                for issue in issues:
                    logger.warning(f"  - {issue}")
            else:
                logger.info("Platform health check: All systems operational")
            
            return report
            
        except Exception as e:
            logger.error(f"Platform health check failed: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'overall_status': 'ERROR',
                'error': str(e),
                'action_required': True
            }
    
    def _get_platform_stats(self) -> dict:
        """Get current platform usage statistics"""
        stats_query = text('''
            SELECT 
                COUNT(DISTINCT user_id_hash) as active_users,
                COUNT(*) as total_expenses,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as recent_expenses,
                COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as last_24h_expenses
            FROM expenses
        ''')
        
        result = db.session.execute(stats_query).fetchone()
        
        return {
            'active_users': result.active_users,
            'total_expenses': result.total_expenses,
            'recent_expenses': result.recent_expenses,
            'last_24h_expenses': result.last_24h_expenses
        }
    
    def _test_sample_users(self) -> dict:
        """Test random sample of existing users"""
        # Get sample of users with varying expense counts
        sample_query = text(f'''
            SELECT user_id_hash, COUNT(*) as expense_count 
            FROM expenses 
            GROUP BY user_id_hash 
            ORDER BY RANDOM() 
            LIMIT {self.sample_size}
        ''')
        
        sample_users = db.session.execute(sample_query).fetchall()
        
        success_count = 0
        test_results = []
        
        for user_hash, expense_count in sample_users:
            result = self._test_user_message_delivery(user_hash, expense_count)
            test_results.append(result)
            if result['success']:
                success_count += 1
        
        success_rate = (success_count / len(sample_users) * 100) if sample_users else 0
        
        return {
            'tested_users': len(sample_users),
            'successful_tests': success_count,
            'success_rate': success_rate,
            'test_details': test_results
        }
    
    def _test_user_message_delivery(self, user_hash: str, expense_count: int) -> dict:
        """Test message delivery for a specific user"""
        try:
            from utils.production_router import production_router
            
            # Test summary request
            response, intent, _, _ = production_router.route_message(
                'summary', user_hash, f'monitor_{int(time.time())}'
            )
            
            # Validate response quality
            has_financial_data = '৳' in response or any(char.isdigit() for char in response)
            no_duplication = response.lower().count('spending across') <= 1
            valid_intent = intent in ['analysis', 'summary']
            appropriate_length = 10 <= len(response) <= 500
            
            # Determine success
            if expense_count > 0:
                # Users with expenses should get financial data
                success = has_financial_data and no_duplication and valid_intent and appropriate_length
            else:
                # Users without expenses should get clean "no data" response
                success = no_duplication and valid_intent and appropriate_length
            
            return {
                'user_hash': user_hash[:8] + '...',
                'expense_count': expense_count,
                'success': success,
                'response_length': len(response),
                'has_financial_data': has_financial_data,
                'no_duplication': no_duplication,
                'valid_intent': valid_intent,
                'intent': intent
            }
            
        except Exception as e:
            return {
                'user_hash': user_hash[:8] + '...',
                'expense_count': expense_count,
                'success': False,
                'error': str(e)
            }
    
    def _test_new_user_compatibility(self) -> dict:
        """Test new user PSID format compatibility"""
        test_psids = [
            '1234567890123456',      # Standard 16-digit
            '123456789012345678',    # 18-digit format  
            '12345678901234',        # 14-digit format
            '1234567890'             # 10-digit minimum
        ]
        
        success_count = 0
        test_results = []
        
        for psid in test_psids:
            result = self._test_psid_format(psid)
            test_results.append(result)
            if result['success']:
                success_count += 1
        
        compatibility_rate = (success_count / len(test_psids) * 100)
        
        return {
            'tested_formats': len(test_psids),
            'successful_formats': success_count,
            'compatibility_rate': compatibility_rate,
            'format_details': test_results
        }
    
    def _test_psid_format(self, psid: str) -> dict:
        """Test specific PSID format compatibility"""
        try:
            from utils.production_router import production_router
            
            # Test router accepts PSID format
            response, intent, _, _ = production_router.route_message(
                'summary', psid, f'format_test_{len(psid)}'
            )
            
            # New users should get clean response
            valid_response = len(response) > 0 and intent == 'analysis'
            no_errors = 'error' not in response.lower()
            
            success = valid_response and no_errors
            
            return {
                'psid_length': len(psid),
                'success': success,
                'response_generated': len(response) > 0,
                'valid_intent': intent == 'analysis',
                'no_errors': no_errors
            }
            
        except Exception as e:
            return {
                'psid_length': len(psid),
                'success': False,
                'error': str(e)
            }
    
    def _detect_issues(self, user_results: dict, new_user_results: dict) -> list[str]:
        """Detect deployment issues requiring attention"""
        issues = []
        
        # Check existing user success rate
        if user_results['success_rate'] < self.success_threshold:
            issues.append(f"Existing user success rate below threshold: {user_results['success_rate']:.1f}%")
        
        # Check new user compatibility
        if new_user_results['compatibility_rate'] < self.success_threshold:
            issues.append(f"New user compatibility below threshold: {new_user_results['compatibility_rate']:.1f}%")
        
        # Check for specific failure patterns
        failed_users = [r for r in user_results['test_details'] if not r['success']]
        if len(failed_users) > 0:
            issues.append(f"{len(failed_users)} users experiencing delivery failures")
        
        # Check for text duplication issues
        duplication_users = [
            r for r in user_results['test_details'] 
            if r.get('no_duplication') == False
        ]
        if len(duplication_users) > 0:
            issues.append(f"{len(duplication_users)} users experiencing text duplication")
        
        return issues

# Global monitor instance
deployment_monitor = DeploymentMonitor()

def run_health_check() -> dict:
    """Run comprehensive platform health check"""
    return deployment_monitor.check_platform_health()

def is_platform_healthy() -> bool:
    """Quick health check - returns True if platform is operational"""
    try:
        report = run_health_check()
        return report.get('overall_status') == 'HEALTHY'
    except Exception:
        return False