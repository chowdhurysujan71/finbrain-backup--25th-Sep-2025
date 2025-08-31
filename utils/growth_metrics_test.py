"""
Growth Metrics Test Suite - Block 4 Implementation
Comprehensive testing for analytics and milestone systems
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class GrowthMetricsTestSuite:
    """
    Comprehensive test suite for Block 4 growth metrics
    Tests both analytics (D1/D3/reports) and milestones (streak-3/10-logs)
    """
    
    def __init__(self):
        self.test_results = []
        self.analytics_enabled = os.getenv('FEATURE_ANALYTICS_BLOCK4', 'true').lower() == 'true'
        self.milestones_enabled = os.getenv('FEATURE_MILESTONES_SIMPLE', 'true').lower() == 'true'
        
    def run_all_tests(self) -> Dict[str, Any]:
        """
        Run comprehensive test suite
        
        Returns:
            dict: Test results summary
        """
        logger.info("Starting Growth Metrics Test Suite...")
        
        # Test 1: Timezone helpers
        self._test_timezone_helpers()
        
        # Test 2: Analytics engine
        self._test_analytics_engine()
        
        # Test 3: Milestone engine  
        self._test_milestone_engine()
        
        # Test 4: Database schema
        self._test_database_schema()
        
        # Test 5: Integration points
        self._test_integration_points()
        
        # Test 6: Feature flags
        self._test_feature_flags()
        
        # Test 7: Telemetry emission
        self._test_telemetry_emission()
        
        # Generate summary
        summary = self._generate_test_summary()
        logger.info(f"Growth Metrics Test Suite completed: {summary['status']}")
        
        return summary
    
    def _test_timezone_helpers(self):
        """Test timezone helper functions"""
        try:
            from utils.timezone_helpers import (
                to_local, day_key, is_same_local_day, 
                local_date_from_datetime, days_between_local,
                is_within_hours, now_local, today_local,
                validate_timezone_helpers
            )
            
            # Basic validation
            validation_result = validate_timezone_helpers()
            self._add_result("Timezone Helpers", "Basic Validation", validation_result)
            
            # Test specific functions
            utc_time = datetime.utcnow()
            local_time = to_local(utc_time)
            self._add_result("Timezone Helpers", "UTC to Local", local_time is not None)
            
            day_string = day_key(local_time)
            self._add_result("Timezone Helpers", "Day Key Generation", isinstance(day_string, str))
            
            same_day = is_same_local_day(utc_time, local_time)
            self._add_result("Timezone Helpers", "Same Day Comparison", isinstance(same_day, bool))
            
            logger.info("✓ Timezone helpers test completed")
            
        except Exception as e:
            self._add_result("Timezone Helpers", "Exception", False, str(e))
            logger.error(f"Timezone helpers test failed: {e}")
    
    def _test_analytics_engine(self):
        """Test analytics engine functionality"""
        try:
            from utils.analytics_engine import (
                analytics_engine, track_d1_activation, 
                track_d3_completion, track_report_request,
                set_user_signup_source, get_user_analytics
            )
            
            # Test engine initialization
            self._add_result("Analytics Engine", "Initialization", analytics_engine is not None)
            self._add_result("Analytics Engine", "Feature Flag", analytics_engine.feature_enabled == self.analytics_enabled)
            
            # Test with mock user data (if database available)
            try:
                from models import User
                mock_user = User()
                mock_user.user_id_hash = "test_user_hash_analytics"
                mock_user.created_at = datetime.utcnow()
                mock_user.expense_count = 0
                mock_user.d1_logged = False
                mock_user.d3_completed = False
                mock_user.reports_requested = 0
                
                # Test analytics functions (dry run)
                analytics_summary = get_user_analytics(mock_user)
                self._add_result("Analytics Engine", "Summary Generation", isinstance(analytics_summary, dict))
                
                logger.info("✓ Analytics engine test completed")
                
            except Exception as db_error:
                self._add_result("Analytics Engine", "Database Test", False, str(db_error))
                logger.warning(f"Analytics database test skipped: {db_error}")
            
        except Exception as e:
            self._add_result("Analytics Engine", "Exception", False, str(e))
            logger.error(f"Analytics engine test failed: {e}")
    
    def _test_milestone_engine(self):
        """Test milestone engine functionality"""
        try:
            from utils.milestone_engine import (
                milestone_engine, update_user_streak,
                check_milestone_nudges, get_milestone_status
            )
            
            # Test engine initialization
            self._add_result("Milestone Engine", "Initialization", milestone_engine is not None)
            self._add_result("Milestone Engine", "Feature Flag", milestone_engine.feature_enabled == self.milestones_enabled)
            
            # Test with mock user data
            try:
                from models import User
                mock_user = User()
                mock_user.user_id_hash = "test_user_hash_milestones"
                mock_user.consecutive_days = 0
                mock_user.expense_count = 0
                mock_user.last_log_date = None
                mock_user.last_milestone_date = None
                
                # Test milestone functions (dry run)
                milestone_status = get_milestone_status(mock_user)
                self._add_result("Milestone Engine", "Status Generation", isinstance(milestone_status, dict))
                
                logger.info("✓ Milestone engine test completed")
                
            except Exception as db_error:
                self._add_result("Milestone Engine", "Database Test", False, str(db_error))
                logger.warning(f"Milestone database test skipped: {db_error}")
            
        except Exception as e:
            self._add_result("Milestone Engine", "Exception", False, str(e))
            logger.error(f"Milestone engine test failed: {e}")
    
    def _test_database_schema(self):
        """Test database schema for growth metrics fields"""
        try:
            from models import User
            from app import db
            
            # Test that new fields exist in User model
            user_fields = dir(User)
            required_fields = [
                'signup_source', 'd1_logged', 'd3_completed', 'reports_requested',
                'last_milestone_date', 'consecutive_days', 'last_log_date'
            ]
            
            for field in required_fields:
                has_field = field in user_fields
                self._add_result("Database Schema", f"Field: {field}", has_field)
            
            # Test database connection and schema
            try:
                from app import app
                with app.app_context():
                    # Simple query to verify schema
                    result = db.session.execute(db.text("SELECT COUNT(*) FROM users")).scalar()
                    self._add_result("Database Schema", "Connection Test", result is not None)
                    
            except Exception as db_error:
                self._add_result("Database Schema", "Connection Test", False, str(db_error))
            
            logger.info("✓ Database schema test completed")
            
        except Exception as e:
            self._add_result("Database Schema", "Exception", False, str(e))
            logger.error(f"Database schema test failed: {e}")
    
    def _test_integration_points(self):
        """Test integration with expense and report handlers"""
        try:
            # Test import of integrated functions
            from utils.db import save_expense
            self._add_result("Integration", "save_expense import", True)
            
            from handlers.summary import handle_summary
            self._add_result("Integration", "handle_summary import", True)
            
            from handlers.insight import handle_insight
            self._add_result("Integration", "handle_insight import", True)
            
            logger.info("✓ Integration points test completed")
            
        except Exception as e:
            self._add_result("Integration", "Exception", False, str(e))
            logger.error(f"Integration points test failed: {e}")
    
    def _test_feature_flags(self):
        """Test feature flag configuration"""
        try:
            analytics_flag = os.getenv('FEATURE_ANALYTICS_BLOCK4', 'true')
            milestones_flag = os.getenv('FEATURE_MILESTONES_SIMPLE', 'true')
            
            self._add_result("Feature Flags", "Analytics Flag Set", analytics_flag in ['true', 'false'])
            self._add_result("Feature Flags", "Milestones Flag Set", milestones_flag in ['true', 'false'])
            
            # Test flag impact on engines
            from utils.analytics_engine import analytics_engine
            from utils.milestone_engine import milestone_engine
            
            expected_analytics = analytics_flag.lower() == 'true'
            expected_milestones = milestones_flag.lower() == 'true'
            
            self._add_result("Feature Flags", "Analytics Engine Respects Flag", analytics_engine.feature_enabled == expected_analytics)
            self._add_result("Feature Flags", "Milestone Engine Respects Flag", milestone_engine.feature_enabled == expected_milestones)
            
            logger.info("✓ Feature flags test completed")
            
        except Exception as e:
            self._add_result("Feature Flags", "Exception", False, str(e))
            logger.error(f"Feature flags test failed: {e}")
    
    def _test_telemetry_emission(self):
        """Test telemetry and structured logging"""
        try:
            from utils.structured import log_analytics_event, log_milestone_event, log_growth_metrics_summary
            
            # Test telemetry function imports
            self._add_result("Telemetry", "Analytics Event Function", callable(log_analytics_event))
            self._add_result("Telemetry", "Milestone Event Function", callable(log_milestone_event))
            self._add_result("Telemetry", "Summary Function", callable(log_growth_metrics_summary))
            
            # Test sample telemetry emission (dry run)
            try:
                sample_data = {"test": True, "timestamp": datetime.utcnow().isoformat()}
                result = log_analytics_event("test_event", "test_user_hash", sample_data)
                self._add_result("Telemetry", "Sample Emission", result)
                
            except Exception as emit_error:
                self._add_result("Telemetry", "Sample Emission", False, str(emit_error))
            
            logger.info("✓ Telemetry emission test completed")
            
        except Exception as e:
            self._add_result("Telemetry", "Exception", False, str(e))
            logger.error(f"Telemetry emission test failed: {e}")
    
    def _add_result(self, category: str, test_name: str, passed: bool, error: Optional[str] = None):
        """Add test result to collection"""
        self.test_results.append({
            "category": category,
            "test": test_name,
            "passed": passed,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def _generate_test_summary(self) -> Dict[str, Any]:
        """Generate comprehensive test summary"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests
        
        # Group by category
        categories = {}
        for result in self.test_results:
            category = result["category"]
            if category not in categories:
                categories[category] = {"total": 0, "passed": 0, "failed": 0}
            
            categories[category]["total"] += 1
            if result["passed"]:
                categories[category]["passed"] += 1
            else:
                categories[category]["failed"] += 1
        
        # Determine overall status
        if failed_tests == 0:
            status = "✅ ALL_TESTS_PASSED"
        elif passed_tests > failed_tests:
            status = "⚠️ MOSTLY_PASSED"
        else:
            status = "❌ MAJOR_FAILURES"
        
        return {
            "status": status,
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": round((passed_tests / total_tests) * 100, 1) if total_tests > 0 else 0
            },
            "categories": categories,
            "feature_flags": {
                "analytics_enabled": self.analytics_enabled,
                "milestones_enabled": self.milestones_enabled
            },
            "failed_tests": [result for result in self.test_results if not result["passed"]],
            "timestamp": datetime.utcnow().isoformat()
        }

# Convenience function for easy testing
def run_growth_metrics_tests() -> Dict[str, Any]:
    """Run complete growth metrics test suite"""
    test_suite = GrowthMetricsTestSuite()
    return test_suite.run_all_tests()

def validate_growth_metrics_deployment() -> bool:
    """
    Validate that growth metrics are properly deployed
    
    Returns:
        bool: True if deployment is valid, False otherwise
    """
    try:
        results = run_growth_metrics_tests()
        
        # Check critical success criteria
        success_rate = results["summary"]["success_rate"]
        critical_failures = any(
            test["category"] in ["Database Schema", "Integration"] and not test["passed"]
            for test in results["failed_tests"]
        )
        
        # Must have >80% success rate and no critical failures
        is_valid = success_rate >= 80.0 and not critical_failures
        
        logger.info(f"Growth metrics deployment validation: {'PASSED' if is_valid else 'FAILED'} "
                   f"(Success rate: {success_rate}%, Critical failures: {critical_failures})")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Growth metrics deployment validation failed: {e}")
        return False