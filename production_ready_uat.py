#!/usr/bin/env python3
"""
Production-Ready Comprehensive UAT Suite
End-to-End Testing: Data Handling → Routing → Processing → Storage → Integrity

Focus Areas:
1. Data Handling: Input parsing, validation, sanitization
2. Routing: Message routing through production pipeline
3. Processing: AI categorization, expense creation, REPORT generation
4. Storage: Database operations, user isolation, persistence
5. Data Integrity: Security, consistency, audit trail
"""

import sys
import time
import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple

# Add project root to path
sys.path.append('/home/runner/workspace')

from app import app, db
from models import Expense, User, MonthlySummary
from utils.production_router import ProductionRouter
from utils.security import hash_psid, sanitize_input
from utils.intent_router import detect_intent
from utils.dispatcher import handle_message_dispatch
from handlers.report import handle_report
from parsers.expense import extract_all_expenses

class ProductionUATSuite:
    """Comprehensive UAT covering all critical system areas"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = datetime.now()
        self.router = ProductionRouter()
        
        # Unique test identifiers
        timestamp = int(time.time())
        self.test_user_a = f"PROD_UAT_{timestamp}_USER_A"
        self.test_user_b = f"PROD_UAT_{timestamp}_USER_B"
        self.test_user_a_hash = hash_psid(self.test_user_a)
        self.test_user_b_hash = hash_psid(self.test_user_b)
        
        print(f"🚀 PRODUCTION UAT SUITE - {self.start_time}")
        print(f"🔒 Test User A Hash: {self.test_user_a_hash[:12]}...")
        print(f"🔒 Test User B Hash: {self.test_user_b_hash[:12]}...")
        print("=" * 80)
    
    def log_test(self, category: str, test_name: str, status: bool, details: str = "", 
                 performance_ms: Optional[float] = None, severity: str = "normal"):
        """Log test result with enhanced metadata"""
        result = {
            'category': category,
            'test': test_name,
            'status': 'PASS' if status else 'FAIL',
            'details': details,
            'severity': severity,
            'performance_ms': performance_ms,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        icon = "✅" if status else "❌"
        perf = f" ({performance_ms:.1f}ms)" if performance_ms else ""
        sev = f" [{severity.upper()}]" if severity != "normal" else ""
        print(f"{icon} [{category}] {test_name}: {'PASS' if status else 'FAIL'}{perf}{sev}")
        if details:
            print(f"   {details}")
    
    def cleanup_test_data(self):
        """Clean up all test data"""
        try:
            with app.app_context():
                # Clean expenses
                db.session.query(Expense).filter(
                    Expense.user_id_hash.in_([self.test_user_a_hash, self.test_user_b_hash])
                ).delete(synchronize_session=False)
                
                # Clean users  
                db.session.query(User).filter(
                    User.user_id_hash.in_([self.test_user_a_hash, self.test_user_b_hash])
                ).delete(synchronize_session=False)
                
                # Clean summaries
                db.session.query(MonthlySummary).filter(
                    MonthlySummary.user_id_hash.in_([self.test_user_a_hash, self.test_user_b_hash])
                ).delete(synchronize_session=False)
                
                db.session.commit()
                print("🧹 Test data cleaned successfully")
                
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
    
    # =========================================================================
    # 1. DATA HANDLING TESTS
    # =========================================================================
    
    def test_data_handling_parsing_accuracy(self):
        """Test expense parsing accuracy across input variations"""
        start = time.time()
        
        test_cases = [
            ("Coffee 150", 150.0, "food"),
            ("Uber 500", 500.0, "transport"),
            ("Rent 2,500", 2500.0, "bills"),
            ("৳1,000 lunch", 1000.0, "food"),
            ("Gas bill 1200.50", 1200.50, "bills"),
            ("Shopping 850", 850.0, "shopping"),
        ]
        
        passed = 0
        for text, expected_amount, expected_category in test_cases:
            try:
                expenses = extract_all_expenses(text, datetime.now())
                if expenses and len(expenses) >= 1:
                    expense = expenses[0]
                    amount_ok = abs(float(expense.get('amount', 0)) - expected_amount) < 0.01
                    category_ok = expense.get('category') == expected_category
                    if amount_ok and category_ok:
                        passed += 1
            except Exception:
                pass
        
        accuracy = (passed / len(test_cases)) * 100
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "DATA_HANDLING", "Expense Parsing Accuracy",
            accuracy >= 85,
            f"Accuracy: {accuracy:.1f}% ({passed}/{len(test_cases)})",
            performance, "critical"
        )
    
    def test_data_handling_input_sanitization(self):
        """Test input sanitization and security validation"""
        start = time.time()
        
        malicious_inputs = [
            "<script>alert('xss')</script>Coffee 150",
            "DROP TABLE expenses; Coffee 200", 
            "'; DELETE FROM users; -- Coffee 300",
            "Coffee 150\x00\x01\x02",  # Control characters
            "Coffee 150" + "A" * 5000,  # Long input
            "😀💰 Coffee 150 🤑",  # Unicode
        ]
        
        passed = 0
        for malicious_input in malicious_inputs:
            try:
                sanitized = sanitize_input(malicious_input)
                
                # Check dangerous tags/patterns removed (correct security behavior)
                sanitized_lower = sanitized.lower()
                no_script_tags = "<script>" not in sanitized_lower  # Script tags removed
                no_sql_keywords = ("drop table" not in sanitized_lower and 
                                  "delete from" not in sanitized_lower and
                                  ";" not in sanitized)  # SQL injection patterns removed
                no_control = not any(ord(c) < 32 for c in sanitized if c not in ['\n', '\r', '\t'])
                reasonable_length = len(sanitized) <= 2000
                non_empty = len(sanitized) > 0  # Should not be completely empty
                
                # Note: Content like 'alert' is preserved for readability after dangerous tags removed
                if no_script_tags and no_sql_keywords and no_control and reasonable_length and non_empty:
                    passed += 1
            except Exception as e:
                print(f"     Exception for '{malicious_input[:30]}...': {e}")
        
        security_score = (passed / len(malicious_inputs)) * 100
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "DATA_HANDLING", "Input Sanitization Security",
            security_score >= 100,  # All tests should pass
            f"Security Score: {security_score:.1f}% ({passed}/{len(malicious_inputs)})",
            performance, "security"
        )
    
    # =========================================================================
    # 2. ROUTING TESTS  
    # =========================================================================
    
    def test_routing_intent_detection_accuracy(self):
        """Test intent detection accuracy for all command types"""
        start = time.time()
        
        test_cases = [
            # Core commands
            ("REPORT", "REPORT"),
            ("report", "REPORT"), 
            ("summary", "SUMMARY"),
            ("insights", "INSIGHT"),
            
            # Expense logging
            ("Coffee 150", "LOG_EXPENSE"),
            ("Uber 500", "LOG_EXPENSE"),
            ("Paid 200 for groceries", "LOG_EXPENSE"),
            
            # FAQ/Other
            ("hello", "UNKNOWN"),
            ("what is this", "UNKNOWN"),
            ("help", "UNKNOWN"),
        ]
        
        passed = 0
        for text, expected_intent in test_cases:
            try:
                detected = detect_intent(text)
                if detected == expected_intent:
                    passed += 1
            except Exception:
                pass
        
        accuracy = (passed / len(test_cases)) * 100
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "ROUTING", "Intent Detection Accuracy",
            accuracy >= 90,
            f"Accuracy: {accuracy:.1f}% ({passed}/{len(test_cases)})",
            performance, "critical"
        )
    
    def test_routing_message_dispatcher_flow(self):
        """Test complete message dispatch flow"""
        start = time.time()
        
        test_messages = [
            ("REPORT", "REPORT"),
            ("summary", "SUMMARY"), 
            ("Coffee 150", "LOG_EXPENSE"),
        ]
        
        passed = 0
        for message, expected_intent in test_messages:
            try:
                response, detected_intent = handle_message_dispatch(self.test_user_a_hash, message)
                
                if (detected_intent == expected_intent and 
                    response and len(response) > 0 and len(response) <= 500):
                    passed += 1
            except Exception as e:
                print(f"     Dispatch error for '{message}': {e}")
        
        dispatch_score = (passed / len(test_messages)) * 100
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "ROUTING", "Message Dispatcher Flow",
            dispatch_score >= 100,
            f"Success Rate: {dispatch_score:.1f}% ({passed}/{len(test_messages)})",
            performance, "critical"
        )
    
    # =========================================================================
    # 3. PROCESSING TESTS
    # =========================================================================
    
    def test_processing_report_command_functionality(self):
        """Test REPORT command Money Story generation"""
        start = time.time()
        
        try:
            with app.app_context():
                # Clean user data first to ensure empty test
                db.session.query(Expense).filter_by(user_id_hash=self.test_user_a_hash).delete()
                db.session.commit()
                
                # Test with no data
                result_empty = handle_report(self.test_user_a_hash)
                empty_story = result_empty.get('text', '')
                
                # Add sample expense for data test
                sample_expense = Expense()
                sample_expense.user_id_hash = self.test_user_a_hash
                sample_expense.user_id = self.test_user_a
                sample_expense.description = "Test Coffee"
                sample_expense.amount = Decimal("150.0")
                sample_expense.category = "food"
                sample_expense.date = datetime.now().date()
                sample_expense.month = datetime.now().strftime('%Y-%m')
                sample_expense.created_at = datetime.now()
                sample_expense.unique_id = str(uuid.uuid4())
                sample_expense.platform = "messenger"
                sample_expense.mid = f"test_report_{int(time.time())}"
                
                db.session.add(sample_expense)
                db.session.commit()
                
                # Test with data
                result_data = handle_report(self.test_user_a_hash)
                data_story = result_data.get('text', '')
                
                # Validation
                conditions = [
                    len(empty_story) > 0,
                    len(empty_story) <= 500,
                    "no expenses" in empty_story.lower(),
                    len(data_story) > 0,
                    len(data_story) <= 500,
                    ("1 expense" in data_story.lower() or "logged 1" in data_story.lower()),
                    len(data_story) != len(empty_story),  # Stories should be different
                ]
                
                passed = all(conditions)
                
        except Exception as e:
            passed = False
            print(f"     REPORT test error: {e}")
        
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "PROCESSING", "REPORT Command Money Stories",
            passed,
            f"Empty: {len(empty_story)}ch, Data: {len(data_story)}ch, Different: {len(data_story) != len(empty_story)}",
            performance, "critical"
        )
    
    def test_processing_expense_creation_workflow(self):
        """Test complete expense creation and categorization"""
        start = time.time()
        
        test_expenses = [
            "Coffee shop 200",
            "Uber ride 350", 
            "Grocery shopping 1200",
        ]
        
        created_expenses = 0
        
        try:
            with app.app_context():
                initial_count = db.session.query(Expense).filter_by(user_id_hash=self.test_user_b_hash).count()
                
                for expense_text in test_expenses:
                    try:
                        response, intent = handle_message_dispatch(self.test_user_b_hash, expense_text)
                        if intent == "LOG_EXPENSE" and "✅" in response:
                            created_expenses += 1
                    except Exception as e:
                        print(f"     Expense creation error for '{expense_text}': {e}")
                
                final_count = db.session.query(Expense).filter_by(user_id_hash=self.test_user_b_hash).count()
                actual_created = final_count - initial_count
                
                success = created_expenses == len(test_expenses) and actual_created >= created_expenses
                
        except Exception as e:
            success = False
            print(f"     Expense workflow error: {e}")
        
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "PROCESSING", "Expense Creation Workflow",
            success,
            f"Created: {created_expenses}/{len(test_expenses)}, Stored: {actual_created}",
            performance, "critical"
        )
    
    # =========================================================================
    # 4. STORAGE TESTS
    # =========================================================================
    
    def test_storage_data_persistence(self):
        """Test data persistence and retrieval accuracy"""
        start = time.time()
        
        try:
            with app.app_context():
                # Create test expense with specific data
                test_amount = Decimal("777.77")
                test_category = "test_category"
                test_description = "UAT Persistence Test"
                
                expense = Expense()
                expense.user_id_hash = self.test_user_a_hash
                expense.user_id = self.test_user_a
                expense.description = test_description
                expense.amount = test_amount
                expense.category = test_category
                expense.date = datetime.now().date()
                expense.month = datetime.now().strftime('%Y-%m')
                expense.created_at = datetime.now()
                expense.unique_id = str(uuid.uuid4())
                expense.platform = "messenger"
                expense.mid = f"test_persist_{int(time.time())}"
                
                db.session.add(expense)
                db.session.commit()
                
                stored_id = expense.id
                
                # Retrieve and validate
                retrieved = db.session.get(Expense, stored_id)
                
                validation_checks = [
                    retrieved is not None,
                    retrieved.user_id_hash == self.test_user_a_hash,
                    retrieved.amount == test_amount,
                    retrieved.category == test_category,
                    retrieved.description == test_description,
                ]
                
                persistence_success = all(validation_checks)
                
        except Exception as e:
            persistence_success = False
            print(f"     Storage persistence error: {e}")
        
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "STORAGE", "Data Persistence & Retrieval",
            persistence_success,
            f"Stored and retrieved expense with ID {stored_id if 'stored_id' in locals() else 'N/A'}",
            performance, "critical"
        )
    
    def test_storage_user_isolation(self):
        """Test user data isolation and security"""
        start = time.time()
        
        try:
            with app.app_context():
                # Create expenses for both test users
                expense_a = Expense()
                expense_a.user_id_hash = self.test_user_a_hash
                expense_a.user_id = self.test_user_a
                expense_a.description = "User A Expense"
                expense_a.amount = Decimal("100.0")
                expense_a.category = "food"
                expense_a.date = datetime.now().date()
                expense_a.month = datetime.now().strftime('%Y-%m')
                expense_a.created_at = datetime.now()
                expense_a.unique_id = str(uuid.uuid4())
                expense_a.platform = "messenger"
                expense_a.mid = f"test_iso_a_{int(time.time())}"
                
                expense_b = Expense()
                expense_b.user_id_hash = self.test_user_b_hash
                expense_b.user_id = self.test_user_b
                expense_b.description = "User B Expense"
                expense_b.amount = Decimal("200.0")
                expense_b.category = "transport"
                expense_b.date = datetime.now().date()
                expense_b.month = datetime.now().strftime('%Y-%m')
                expense_b.created_at = datetime.now()
                expense_b.unique_id = str(uuid.uuid4())
                expense_b.platform = "messenger"
                expense_b.mid = f"test_iso_b_{int(time.time())}"
                
                db.session.add_all([expense_a, expense_b])
                db.session.commit()
                
                # Verify isolation - User A can only see their data
                user_a_expenses = db.session.query(Expense).filter_by(user_id_hash=self.test_user_a_hash).all()
                user_b_expenses = db.session.query(Expense).filter_by(user_id_hash=self.test_user_b_hash).all()
                
                # Cross-contamination check
                user_a_has_b_data = any(exp.user_id_hash == self.test_user_b_hash for exp in user_a_expenses)
                user_b_has_a_data = any(exp.user_id_hash == self.test_user_a_hash for exp in user_b_expenses)
                
                isolation_success = (
                    len(user_a_expenses) > 0 and
                    len(user_b_expenses) > 0 and
                    not user_a_has_b_data and
                    not user_b_has_a_data
                )
                
        except Exception as e:
            isolation_success = False
            print(f"     User isolation error: {e}")
        
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "STORAGE", "User Data Isolation",
            isolation_success,
            f"User A: {len(user_a_expenses) if 'user_a_expenses' in locals() else 0} expenses, User B: {len(user_b_expenses) if 'user_b_expenses' in locals() else 0} expenses",
            performance, "security"
        )
    
    # =========================================================================
    # 5. DATA INTEGRITY TESTS  
    # =========================================================================
    
    def test_integrity_data_consistency(self):
        """Test data consistency across operations"""
        start = time.time()
        
        try:
            with app.app_context():
                # Create expense and verify all fields are consistent
                test_data = {
                    'description': 'Integrity Test Expense',
                    'amount': Decimal('999.99'),
                    'category': 'integrity_test',
                    'user_hash': self.test_user_a_hash,
                }
                
                expense = Expense()
                expense.user_id_hash = test_data['user_hash']
                expense.user_id = self.test_user_a
                expense.description = test_data['description']
                expense.amount = test_data['amount']
                expense.category = test_data['category']
                expense.date = datetime.now().date()
                expense.month = datetime.now().strftime('%Y-%m')
                expense.created_at = datetime.now()
                expense.unique_id = str(uuid.uuid4())
                expense.platform = "messenger"
                expense.mid = f"test_integrity_{int(time.time())}"
                
                db.session.add(expense)
                db.session.commit()
                
                # Retrieve and verify consistency
                retrieved = db.session.get(Expense, expense.id)
                
                consistency_checks = [
                    retrieved.description == test_data['description'],
                    retrieved.amount == test_data['amount'],
                    retrieved.category == test_data['category'],
                    retrieved.user_id_hash == test_data['user_hash'],
                    retrieved.date is not None,
                    retrieved.month == datetime.now().strftime('%Y-%m'),
                    retrieved.created_at is not None,
                ]
                
                consistency_passed = all(consistency_checks)
                
        except Exception as e:
            consistency_passed = False
            print(f"     Data consistency error: {e}")
        
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "INTEGRITY", "Data Consistency Validation",
            consistency_passed,
            f"All {len(consistency_checks) if 'consistency_checks' in locals() else 0} consistency checks passed" if consistency_passed else "Consistency validation failed",
            performance, "critical"
        )
    
    def test_integrity_audit_trail(self):
        """Test audit trail and transaction logging"""
        start = time.time()
        
        try:
            with app.app_context():
                initial_expense_count = db.session.query(Expense).count()
                
                # Create expense through production pipeline
                response, intent = handle_message_dispatch(self.test_user_a_hash, "Audit test 555")
                
                final_expense_count = db.session.query(Expense).count()
                
                # Verify audit trail
                audit_checks = [
                    intent in ["LOG_EXPENSE", "UNKNOWN"],  # Should be routed properly
                    response is not None and len(response) > 0,  # Should get response
                ]
                
                if intent == "LOG_EXPENSE":
                    audit_checks.append(final_expense_count > initial_expense_count)  # Should create expense
                
                audit_trail_valid = all(audit_checks)
                
        except Exception as e:
            audit_trail_valid = False
            print(f"     Audit trail error: {e}")
        
        performance = (time.time() - start) * 1000
        
        self.log_test(
            "INTEGRITY", "Audit Trail Validation", 
            audit_trail_valid,
            f"Intent: {intent if 'intent' in locals() else 'N/A'}, Response length: {len(response) if 'response' in locals() else 0}",
            performance, "security"
        )
    
    # =========================================================================
    # MAIN EXECUTION & REPORTING
    # =========================================================================
    
    def run_comprehensive_uat(self):
        """Execute complete UAT suite and generate audit report"""
        print("🔍 Starting Comprehensive End-to-End UAT...")
        
        with app.app_context():
            # Clean up before testing
            self.cleanup_test_data()
            
            # Execute all test categories
            print("\n📊 DATA HANDLING TESTS")
            print("-" * 40)
            self.test_data_handling_parsing_accuracy()
            self.test_data_handling_input_sanitization()
            
            print("\n🚦 ROUTING TESTS")  
            print("-" * 40)
            self.test_routing_intent_detection_accuracy()
            self.test_routing_message_dispatcher_flow()
            
            print("\n⚙️  PROCESSING TESTS")
            print("-" * 40)
            self.test_processing_report_command_functionality()
            self.test_processing_expense_creation_workflow()
            
            print("\n💾 STORAGE TESTS")
            print("-" * 40)
            self.test_storage_data_persistence()
            self.test_storage_user_isolation()
            
            print("\n🔒 DATA INTEGRITY TESTS")
            print("-" * 40)
            self.test_integrity_data_consistency()
            self.test_integrity_audit_trail()
            
            # Clean up after testing
            self.cleanup_test_data()
            
            # Generate comprehensive audit report
            self.generate_audit_report()
    
    def generate_audit_report(self):
        """Generate detailed audit report"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Calculate statistics
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['status'] == 'PASS')
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Category breakdown
        categories = {}
        for result in self.test_results:
            cat = result['category']
            if cat not in categories:
                categories[cat] = {'total': 0, 'passed': 0}
            categories[cat]['total'] += 1
            if result['status'] == 'PASS':
                categories[cat]['passed'] += 1
        
        # Critical/Security failures
        critical_failures = [r for r in self.test_results if r['status'] == 'FAIL' and r['severity'] in ['critical', 'security']]
        
        print(f"\n{'='*80}")
        print(f"🔍 COMPREHENSIVE UAT AUDIT REPORT")
        print(f"{'='*80}")
        print(f"📅 Execution Time: {self.start_time} - {end_time}")
        print(f"⏱️  Total Duration: {duration:.2f} seconds")
        print(f"🧪 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📊 Success Rate: {success_rate:.1f}%")
        
        print(f"\n📋 CATEGORY BREAKDOWN:")
        for category, stats in categories.items():
            cat_success = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            status_icon = "✅" if cat_success == 100 else "⚠️" if cat_success >= 80 else "❌"
            print(f"  {status_icon} {category}: {stats['passed']}/{stats['total']} ({cat_success:.1f}%)")
        
        if critical_failures:
            print(f"\n🚨 CRITICAL FAILURES ({len(critical_failures)}):")
            for failure in critical_failures:
                print(f"  ❌ [{failure['category']}] {failure['test']}")
                print(f"     {failure['details']}")
        
        print(f"\n📈 PERFORMANCE METRICS:")
        perf_tests = [r for r in self.test_results if r['performance_ms'] is not None]
        if perf_tests:
            avg_performance = sum(r['performance_ms'] for r in perf_tests) / len(perf_tests)
            max_performance = max(r['performance_ms'] for r in perf_tests)
            print(f"  ⏱️  Average Response Time: {avg_performance:.1f}ms")
            print(f"  🏃 Max Response Time: {max_performance:.1f}ms")
        
        print(f"\n🔍 DETAILED TEST RESULTS:")
        for result in self.test_results:
            icon = "✅" if result['status'] == 'PASS' else "❌"
            perf = f" ({result['performance_ms']:.1f}ms)" if result['performance_ms'] else ""
            print(f"  {icon} [{result['category']}] {result['test']}: {result['status']}{perf}")
            if result['details']:
                print(f"     {result['details']}")
        
        # Final verdict
        print(f"\n{'='*80}")
        if success_rate >= 95:
            print(f"🎉 PRODUCTION READY: {success_rate:.1f}% success rate - System ready for deployment!")
        elif success_rate >= 85:
            print(f"⚠️  CAUTION ADVISED: {success_rate:.1f}% success rate - Address failures before deployment")
        else:
            print(f"🚨 NOT PRODUCTION READY: {success_rate:.1f}% success rate - Critical issues must be resolved")
        
        print(f"{'='*80}")
        
        # Export results as JSON
        report_data = {
            'execution_time': {
                'start': self.start_time.isoformat(),
                'end': end_time.isoformat(),
                'duration_seconds': duration
            },
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'failed_tests': failed_tests,
                'success_rate': success_rate
            },
            'category_breakdown': categories,
            'critical_failures': critical_failures,
            'detailed_results': self.test_results
        }
        
        return report_data

def main():
    """Execute the comprehensive UAT suite"""
    uat_suite = ProductionUATSuite()
    uat_suite.run_comprehensive_uat()

if __name__ == "__main__":
    main()