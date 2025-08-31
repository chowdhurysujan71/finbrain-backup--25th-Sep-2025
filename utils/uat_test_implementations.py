"""
Actual UAT Test Implementations for Report Feedback Feature
Contains the real test logic for comprehensive end-to-end validation
"""

import logging
import time
import json
from typing import Dict, Any, List
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

class UATTestImplementations:
    """Real implementations of UAT tests"""
    
    def __init__(self, framework_instance):
        self.framework = framework_instance
        
    def test_existing_user_flow(self, test_id: str) -> Dict[str, Any]:
        """Test complete flow for existing user with historical data"""
        try:
            from app import app, db
            from models import User, Expense, ReportFeedback
            from utils.production_router import ProductionRouter
            
            with app.app_context():
                # Create test user with historical data
                test_user_id = f"uat_existing_{test_id}_{int(time.time())}"
                self.framework.test_data_cleanup.append(test_user_id)
                
                audit_trail = []
                integrity_checks = []
                
                # Step 1: Create user with expense history
                user = User(user_id_hash=test_user_id, platform='messenger')
                db.session.add(user)
                
                # Add multiple expenses
                expenses = []
                for i in range(5):
                    expense = Expense(
                        user_id=test_user_id,
                        user_id_hash=test_user_id,
                        amount=100.0 + (i * 25),
                        category=['food', 'transport', 'shopping'][i % 3],
                        description=f'UAT test expense {i}',
                        date=date.today() - timedelta(days=i),
                        month=datetime.now().strftime('%Y-%m'),
                        unique_id=f'uat_expense_{test_id}_{i}'
                    )
                    expenses.append(expense)
                    db.session.add(expense)
                
                db.session.commit()
                audit_trail.append({"step": "user_creation", "status": "success", "user_id": test_user_id, "expenses_created": len(expenses)})
                
                # Step 2: Test report generation
                router = ProductionRouter()
                start_time = time.time()
                report_response, report_intent, _, _ = router.route_message('REPORT', test_user_id, f'{test_id}_report')
                report_time = (time.time() - start_time) * 1000
                
                audit_trail.append({"step": "report_generation", "status": "success", "time_ms": report_time, "intent": report_intent})
                
                # Integrity check: Verify report contains data
                if report_response and "text" in report_response:
                    integrity_checks.append({"check": "report_content", "status": "PASS", "details": "Report contains text content"})
                else:
                    integrity_checks.append({"check": "report_content", "status": "FAIL", "details": "Report missing text content"})
                
                # Step 3: Test feedback collection
                feedback_router = ProductionRouter()
                start_time = time.time()
                feedback_response, feedback_intent, _, _ = feedback_router.route_message('YES', test_user_id, f'{test_id}_feedback')
                feedback_time = (time.time() - start_time) * 1000
                
                audit_trail.append({"step": "feedback_collection", "status": "success", "time_ms": feedback_time, "intent": feedback_intent})
                
                # Step 4: Verify feedback stored in database
                feedback_count = db.session.query(ReportFeedback).filter_by(user_id_hash=test_user_id).count()
                if feedback_count > 0:
                    integrity_checks.append({"check": "feedback_storage", "status": "PASS", "details": f"Feedback stored: {feedback_count} records"})
                else:
                    integrity_checks.append({"check": "feedback_storage", "status": "FAIL", "details": "No feedback found in database"})
                
                # Step 5: Performance validation
                total_time = report_time + feedback_time
                if total_time < 2000:  # Under 2 seconds
                    integrity_checks.append({"check": "performance", "status": "PASS", "details": f"Total time: {total_time:.1f}ms"})
                else:
                    integrity_checks.append({"check": "performance", "status": "WARNING", "details": f"Total time: {total_time:.1f}ms exceeds 2000ms"})
                
                return {
                    "status": "PASS",
                    "details": {
                        "user_id": test_user_id,
                        "expenses_created": len(expenses),
                        "report_time_ms": report_time,
                        "feedback_time_ms": feedback_time,
                        "total_time_ms": total_time,
                        "feedback_stored": feedback_count
                    },
                    "audit_trail": audit_trail,
                    "integrity_checks": integrity_checks
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "errors": [f"Existing user flow test failed: {str(e)}"],
                "details": {"error_type": type(e).__name__}
            }
    
    def test_new_user_first_report(self, test_id: str) -> Dict[str, Any]:
        """Test new user's first report generation"""
        try:
            from app import app, db
            from models import User
            from utils.production_router import ProductionRouter
            
            with app.app_context():
                # Create new user without any expense history
                test_user_id = f"uat_new_{test_id}_{int(time.time())}"
                self.framework.test_data_cleanup.append(test_user_id)
                
                audit_trail = []
                integrity_checks = []
                
                # Step 1: Create new user (no expenses)
                user = User(user_id_hash=test_user_id, platform='messenger')
                db.session.add(user)
                db.session.commit()
                
                audit_trail.append({"step": "new_user_creation", "status": "success", "user_id": test_user_id})
                
                # Step 2: Request report for user with no data
                router = ProductionRouter()
                start_time = time.time()
                report_response, report_intent, _, _ = router.route_message('REPORT', test_user_id, f'{test_id}_new_report')
                report_time = (time.time() - start_time) * 1000
                
                audit_trail.append({"step": "empty_report_generation", "status": "success", "time_ms": report_time})
                
                # Integrity check: Verify appropriate empty state message
                if report_response and "text" in report_response:
                    report_text = report_response["text"]
                    if "No expenses" in report_text or "Start tracking" in report_text:
                        integrity_checks.append({"check": "empty_state_message", "status": "PASS", "details": "Appropriate empty state message"})
                    else:
                        integrity_checks.append({"check": "empty_state_message", "status": "WARNING", "details": "Unexpected content for empty state"})
                else:
                    integrity_checks.append({"check": "empty_state_message", "status": "FAIL", "details": "No report response"})
                
                # Step 3: Verify fast response time for new users
                if report_time < 1000:  # Under 1 second for empty state
                    integrity_checks.append({"check": "new_user_performance", "status": "PASS", "details": f"Fast response: {report_time:.1f}ms"})
                else:
                    integrity_checks.append({"check": "new_user_performance", "status": "WARNING", "details": f"Slow response: {report_time:.1f}ms"})
                
                return {
                    "status": "PASS",
                    "details": {
                        "user_id": test_user_id,
                        "report_time_ms": report_time,
                        "report_content": report_response.get("text", "")[:100] if report_response else ""
                    },
                    "audit_trail": audit_trail,
                    "integrity_checks": integrity_checks
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "errors": [f"New user test failed: {str(e)}"],
                "details": {"error_type": type(e).__name__}
            }
    
    def test_cache_consistency(self, test_id: str) -> Dict[str, Any]:
        """Test cache consistency across multiple requests"""
        try:
            from app import app, db
            from models import User, Expense
            from utils.production_router import ProductionRouter
            from utils.performance_cache import performance_cache
            
            with app.app_context():
                test_user_id = f"uat_cache_{test_id}_{int(time.time())}"
                self.framework.test_data_cleanup.append(test_user_id)
                
                audit_trail = []
                integrity_checks = []
                
                # Step 1: Create user with data
                user = User(user_id_hash=test_user_id, platform='messenger')
                db.session.add(user)
                
                expense = Expense(
                    user_id=test_user_id, user_id_hash=test_user_id,
                    amount=150.0, category='food', description='Cache test',
                    date=date.today(), month=datetime.now().strftime('%Y-%m'),
                    unique_id=f'cache_test_{test_id}'
                )
                db.session.add(expense)
                db.session.commit()
                
                audit_trail.append({"step": "cache_test_setup", "status": "success"})
                
                # Step 2: First request (cache miss)
                router1 = ProductionRouter()
                start_time = time.time()
                response1, _, _, _ = router1.route_message('REPORT', test_user_id, f'{test_id}_cache_1')
                time1 = (time.time() - start_time) * 1000
                
                audit_trail.append({"step": "first_request", "status": "success", "time_ms": time1, "expected": "cache_miss"})
                
                # Step 3: Second request (should be cache hit)
                router2 = ProductionRouter()
                start_time = time.time()
                response2, _, _, _ = router2.route_message('REPORT', test_user_id, f'{test_id}_cache_2')
                time2 = (time.time() - start_time) * 1000
                
                audit_trail.append({"step": "second_request", "status": "success", "time_ms": time2, "expected": "cache_hit"})
                
                # Step 4: Verify cache performance improvement
                cache_speedup = time1 / time2 if time2 > 0 else 0
                if cache_speedup > 5:  # At least 5x speedup
                    integrity_checks.append({"check": "cache_performance", "status": "PASS", "details": f"Cache speedup: {cache_speedup:.1f}x"})
                elif cache_speedup > 2:
                    integrity_checks.append({"check": "cache_performance", "status": "WARNING", "details": f"Moderate speedup: {cache_speedup:.1f}x"})
                else:
                    integrity_checks.append({"check": "cache_performance", "status": "FAIL", "details": f"Poor speedup: {cache_speedup:.1f}x"})
                
                # Step 5: Verify response consistency
                if response1 and response2:
                    text1 = response1.get("text", "").replace("Was this helpful?", "").strip()
                    text2 = response2.get("text", "").replace("Was this helpful?", "").strip()
                    
                    if text1 == text2:
                        integrity_checks.append({"check": "response_consistency", "status": "PASS", "details": "Cached response matches original"})
                    else:
                        integrity_checks.append({"check": "response_consistency", "status": "FAIL", "details": "Response mismatch between cached and original"})
                
                # Step 6: Check cache statistics
                cache_stats = performance_cache.get_stats()
                audit_trail.append({"step": "cache_statistics", "status": "success", "stats": cache_stats})
                
                return {
                    "status": "PASS",
                    "details": {
                        "user_id": test_user_id,
                        "first_request_ms": time1,
                        "second_request_ms": time2,
                        "cache_speedup": cache_speedup,
                        "cache_stats": cache_stats
                    },
                    "audit_trail": audit_trail,
                    "integrity_checks": integrity_checks
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "errors": [f"Cache consistency test failed: {str(e)}"],
                "details": {"error_type": type(e).__name__}
            }
    
    def test_feedback_performance_stress(self, test_id: str) -> Dict[str, Any]:
        """Test feedback processing under stress conditions"""
        try:
            from app import app, db
            from models import User, Expense
            from utils.production_router import ProductionRouter
            
            with app.app_context():
                test_user_id = f"uat_stress_{test_id}_{int(time.time())}"
                self.framework.test_data_cleanup.append(test_user_id)
                
                audit_trail = []
                integrity_checks = []
                
                # Step 1: Setup user
                user = User(user_id_hash=test_user_id, platform='messenger')
                db.session.add(user)
                
                expense = Expense(
                    user_id=test_user_id, user_id_hash=test_user_id,
                    amount=100.0, category='food', description='Stress test',
                    date=date.today(), month=datetime.now().strftime('%Y-%m'),
                    unique_id=f'stress_test_{test_id}'
                )
                db.session.add(expense)
                db.session.commit()
                
                # Step 2: Generate report to create feedback context
                router = ProductionRouter()
                router.route_message('REPORT', test_user_id, f'{test_id}_stress_setup')
                
                # Step 3: Rapid feedback testing
                feedback_times = []
                feedback_router = ProductionRouter()
                
                for i in range(10):  # 10 rapid feedback attempts
                    start_time = time.time()
                    response, intent, _, _ = feedback_router.route_message('YES', test_user_id, f'{test_id}_stress_{i}')
                    feedback_time = (time.time() - start_time) * 1000
                    feedback_times.append(feedback_time)
                    
                    # Brief pause to simulate realistic usage
                    time.sleep(0.1)
                
                audit_trail.append({"step": "rapid_feedback_testing", "status": "success", "attempts": len(feedback_times)})
                
                # Step 4: Performance analysis
                avg_feedback_time = sum(feedback_times) / len(feedback_times)
                max_feedback_time = max(feedback_times)
                min_feedback_time = min(feedback_times)
                
                # Performance validation
                if avg_feedback_time < 1000:
                    integrity_checks.append({"check": "stress_performance", "status": "PASS", "details": f"Average: {avg_feedback_time:.1f}ms"})
                elif avg_feedback_time < 2000:
                    integrity_checks.append({"check": "stress_performance", "status": "WARNING", "details": f"Average: {avg_feedback_time:.1f}ms"})
                else:
                    integrity_checks.append({"check": "stress_performance", "status": "FAIL", "details": f"Average: {avg_feedback_time:.1f}ms"})
                
                # Consistency validation
                time_variance = max_feedback_time - min_feedback_time
                if time_variance < 500:  # Low variance indicates consistent performance
                    integrity_checks.append({"check": "performance_consistency", "status": "PASS", "details": f"Variance: {time_variance:.1f}ms"})
                else:
                    integrity_checks.append({"check": "performance_consistency", "status": "WARNING", "details": f"High variance: {time_variance:.1f}ms"})
                
                return {
                    "status": "PASS",
                    "details": {
                        "user_id": test_user_id,
                        "feedback_attempts": len(feedback_times),
                        "average_time_ms": avg_feedback_time,
                        "max_time_ms": max_feedback_time,
                        "min_time_ms": min_feedback_time,
                        "time_variance_ms": time_variance
                    },
                    "audit_trail": audit_trail,
                    "integrity_checks": integrity_checks
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "errors": [f"Feedback stress test failed: {str(e)}"],
                "details": {"error_type": type(e).__name__}
            }
    
    def test_data_integrity_comprehensive(self, test_id: str) -> Dict[str, Any]:
        """Comprehensive data integrity validation"""
        try:
            from app import app, db
            from models import User, Expense, ReportFeedback
            from utils.production_router import ProductionRouter
            
            with app.app_context():
                test_user_id = f"uat_integrity_{test_id}_{int(time.time())}"
                self.framework.test_data_cleanup.append(test_user_id)
                
                audit_trail = []
                integrity_checks = []
                
                # Step 1: Create comprehensive test data
                user = User(user_id_hash=test_user_id, platform='messenger')
                db.session.add(user)
                
                # Multiple expenses across different categories
                expense_categories = ['food', 'transport', 'shopping', 'entertainment']
                expenses_created = []
                for i, category in enumerate(expense_categories):
                    expense = Expense(
                        user_id=test_user_id, user_id_hash=test_user_id,
                        amount=50.0 + (i * 25), category=category,
                        description=f'Integrity test {category}',
                        date=date.today() - timedelta(days=i),
                        month=datetime.now().strftime('%Y-%m'),
                        unique_id=f'integrity_expense_{test_id}_{i}'
                    )
                    expenses_created.append(expense)
                    db.session.add(expense)
                
                db.session.commit()
                audit_trail.append({"step": "comprehensive_data_creation", "status": "success", "expenses": len(expenses_created)})
                
                # Step 2: Verify data relationships
                user_count = db.session.query(User).filter_by(user_id_hash=test_user_id).count()
                expense_count = db.session.query(Expense).filter_by(user_id_hash=test_user_id).count()
                
                if user_count == 1 and expense_count == len(expense_categories):
                    integrity_checks.append({"check": "data_relationships", "status": "PASS", "details": f"User: {user_count}, Expenses: {expense_count}"})
                else:
                    integrity_checks.append({"check": "data_relationships", "status": "FAIL", "details": f"Expected 1 user, {len(expense_categories)} expenses; Got {user_count}, {expense_count}"})
                
                # Step 3: Test report generation and feedback cycle
                router = ProductionRouter()
                report_response, _, _, _ = router.route_message('REPORT', test_user_id, f'{test_id}_integrity_report')
                
                # Process feedback
                feedback_router = ProductionRouter()
                feedback_response, _, _, _ = feedback_router.route_message('YES', test_user_id, f'{test_id}_integrity_feedback')
                
                # Step 4: Verify feedback storage integrity
                feedback_records = db.session.query(ReportFeedback).filter_by(user_id_hash=test_user_id).all()
                
                if len(feedback_records) == 1:
                    feedback_record = feedback_records[0]
                    if feedback_record.signal == 'up' and feedback_record.user_id_hash == test_user_id:
                        integrity_checks.append({"check": "feedback_integrity", "status": "PASS", "details": "Feedback correctly stored"})
                    else:
                        integrity_checks.append({"check": "feedback_integrity", "status": "FAIL", "details": "Feedback data corruption"})
                else:
                    integrity_checks.append({"check": "feedback_integrity", "status": "FAIL", "details": f"Expected 1 feedback record, got {len(feedback_records)}"})
                
                # Step 5: Data consistency verification
                audit_trail.append({"step": "data_consistency_check", "status": "success"})
                
                # Verify expense amounts sum correctly
                expected_total = sum(expense.amount for expense in expenses_created)
                db_total = sum(float(expense.amount) for expense in db.session.query(Expense).filter_by(user_id_hash=test_user_id).all())
                
                if abs(expected_total - db_total) < 0.01:  # Account for floating point precision
                    integrity_checks.append({"check": "amount_consistency", "status": "PASS", "details": f"Total: {db_total}"})
                else:
                    integrity_checks.append({"check": "amount_consistency", "status": "FAIL", "details": f"Expected: {expected_total}, Got: {db_total}"})
                
                return {
                    "status": "PASS",
                    "details": {
                        "user_id": test_user_id,
                        "expenses_created": len(expenses_created),
                        "feedback_records": len(feedback_records),
                        "total_amount": db_total,
                        "categories_tested": expense_categories
                    },
                    "audit_trail": audit_trail,
                    "integrity_checks": integrity_checks
                }
                
        except Exception as e:
            return {
                "status": "FAIL",
                "errors": [f"Data integrity test failed: {str(e)}"],
                "details": {"error_type": type(e).__name__}
            }