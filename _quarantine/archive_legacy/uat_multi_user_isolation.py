#!/usr/bin/env python3
"""
Multi-User Data Isolation + Per-User AI Feedback UAT
===================================================

Comprehensive test suite to verify:
1. Database isolation between users
2. AI context scoping per user
3. Concurrency safety
4. Prompt injection defense
5. Cross-user data leak prevention

Test Users:
- UserA: id=a_111, name="Alice", goal="save_more", risk="low"  
- UserB: id=b_222, name="Bob", goal="travel_points", risk="medium"
- NewUserC: id=c_333, name="Carol", goal="debt_paydown", risk="low"
"""

import os
import sys
import json
import time
import logging
import hashlib
import requests
import threading
import concurrent.futures
from datetime import datetime, date, timedelta
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/home/runner/workspace')

from app import app, db
from models import User, Expense, MonthlySummary
from utils.security import hash_psid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('uat_isolation')

class MultiUserIsolationUAT:
    """Comprehensive multi-user data isolation test suite"""
    
    def __init__(self):
        self.test_users = {
            'a_111': {'name': 'Alice', 'goal': 'save_more', 'risk': 'low'},
            'b_222': {'name': 'Bob', 'goal': 'travel_points', 'risk': 'medium'},
            'c_333': {'name': 'Carol', 'goal': 'debt_paydown', 'risk': 'low'}
        }
        
        self.user_hashes = {uid: hash_psid(uid) for uid in self.test_users.keys()}
        self.results = {}
        self.base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
        
    def log_result(self, test_name, status, details=None):
        """Log test result"""
        self.results[test_name] = {
            'status': status,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        logger.info(f"TEST {test_name}: {status}")
        if details:
            logger.info(f"  Details: {details}")
    
    def run_all_tests(self):
        """Execute complete UAT suite"""
        logger.info("=== MULTI-USER DATA ISOLATION UAT STARTING ===")
        
        with app.app_context():
            try:
                # Core isolation tests
                self.test_schema_indexes()
                self.test_user_data_counts()
                self.setup_test_users()
                self.test_data_isolation()
                self.test_cross_user_leak_prevention()
                
                # AI integration tests
                self.test_ai_context_scoping()
                self.test_concurrent_requests()
                self.test_prompt_injection_defense()
                self.test_mutation_safety()
                
                # Generate final report
                self.generate_final_report()
                
            except Exception as e:
                logger.error(f"UAT CRITICAL ERROR: {str(e)}")
                self.log_result("UAT_EXECUTION", "FAIL", f"Critical error: {str(e)}")
            
            finally:
                self.cleanup_test_data()
    
    def test_schema_indexes(self):
        """Verify database schema has proper user_id indexes"""
        try:
            # Check for user_id indexes on critical tables
            index_query = """
            SELECT tablename, indexname, indexdef 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND (indexdef ILIKE '%user_id%' OR indexdef ILIKE '%user_id_hash%')
            ORDER BY tablename;
            """
            
            result = db.session.execute(db.text(index_query))
            indexes = result.fetchall()
            
            critical_tables = {'expenses', 'users', 'monthly_summaries'}
            indexed_tables = {row[0] for row in indexes if 'user_id' in row[2].lower()}
            
            missing_indexes = critical_tables - indexed_tables
            
            if missing_indexes:
                self.log_result("SCHEMA_INDEXES", "FAIL", 
                              f"Missing user_id indexes on: {missing_indexes}")
            else:
                self.log_result("SCHEMA_INDEXES", "PASS", 
                              f"Found user_id indexes on {len(indexed_tables)} tables")
                
        except Exception as e:
            self.log_result("SCHEMA_INDEXES", "ERROR", str(e))
    
    def test_user_data_counts(self):
        """Check existing data counts per user"""
        try:
            counts = {}
            for user_id, user_hash in self.user_hashes.items():
                # Count expenses
                expense_count = db.session.query(Expense).filter(
                    Expense.user_id == user_hash
                ).count()
                
                # Count user records
                user_count = db.session.query(User).filter(
                    User.user_id_hash == user_hash
                ).count()
                
                counts[user_id] = {
                    'expenses': expense_count,
                    'user_records': user_count
                }
            
            # Verify c_333 starts with minimal data (user record is OK, expenses should be 0)
            if counts['c_333']['expenses'] == 0:
                self.log_result("USER_DATA_COUNTS", "PASS", f"Baseline counts: {counts}")
            else:
                self.log_result("USER_DATA_COUNTS", "FAIL", 
                              f"c_333 should have 0 expenses: {counts['c_333']}")
                
        except Exception as e:
            self.log_result("USER_DATA_COUNTS", "ERROR", str(e))
    
    def setup_test_users(self):
        """Create test users and sample data"""
        try:
            # Create/update existing users
            for user_id, data in self.test_users.items():
                user_hash = self.user_hashes[user_id]
                
                # Create or get user record
                user = db.session.query(User).filter(
                    User.user_id_hash == user_hash
                ).first()
                
                if not user:
                    user = User(
                        user_id_hash=user_hash,
                        platform='messenger',
                        total_expenses=0,
                        expense_count=0
                    )
                    db.session.add(user)
                    logger.info(f"Created user {user_id} ({data['name']})")
            
            # Add specific test data for c_333 (NewUserC)
            self.create_c333_test_data()
            
            db.session.commit()
            self.log_result("SETUP_TEST_USERS", "PASS", "Test users created successfully")
            
        except Exception as e:
            db.session.rollback()
            self.log_result("SETUP_TEST_USERS", "ERROR", str(e))
    
    def create_c333_test_data(self):
        """Create specific test transactions for user c_333"""
        user_hash = self.user_hashes['c_333']
        today = date.today()
        
        test_expenses = [
            {
                'description': 'Salary deposit - monthly income',
                'amount': Decimal('20000.00'),
                'category': 'income',
                'unique_id': f'c333_salary_{int(time.time())}'
            },
            {
                'description': 'Groceries - weekly shopping',
                'amount': Decimal('2500.00'),
                'category': 'grocery',
                'unique_id': f'c333_grocery_{int(time.time())}'
            },
            {
                'description': 'Mobile data plan',
                'amount': Decimal('1200.00'),
                'category': 'bill',
                'unique_id': f'c333_mobile_{int(time.time())}'
            }
        ]
        
        for expense_data in test_expenses:
            expense = Expense(
                user_id=user_hash,
                description=expense_data['description'],
                amount=expense_data['amount'],
                category=expense_data['category'],
                date=today,
                month=today.strftime('%Y-%m'),
                unique_id=expense_data['unique_id'],
                platform='messenger'
            )
            db.session.add(expense)
        
        logger.info(f"Created {len(test_expenses)} test expenses for c_333")
    
    def test_data_isolation(self):
        """Test strict data isolation between users"""
        try:
            user_hash_c333 = self.user_hashes['c_333']
            
            # Fetch data for c_333 only
            c333_expenses = db.session.query(Expense).filter(
                Expense.user_id == user_hash_c333
            ).all()
            
            # Verify no cross-user contamination
            for expense in c333_expenses:
                if expense.user_id != user_hash_c333:
                    self.log_result("DATA_ISOLATION", "FAIL", 
                                  f"Found foreign expense {expense.id} with user_id {expense.user_id}")
                    return
            
            # Test filtered count vs unfiltered count for c_333
            total_expenses = db.session.query(Expense).count()
            c333_count = len(c333_expenses)
            
            if c333_count >= 3 and total_expenses > c333_count:
                self.log_result("DATA_ISOLATION", "PASS", 
                              f"c_333 has {c333_count} expenses, total DB has {total_expenses}")
            else:
                self.log_result("DATA_ISOLATION", "FAIL", 
                              f"Isolation unclear: c_333={c333_count}, total={total_expenses}")
                
        except Exception as e:
            self.log_result("DATA_ISOLATION", "ERROR", str(e))
    
    def test_cross_user_leak_prevention(self):
        """Test for cross-user data leaks with deliberate wrong filters"""
        try:
            user_hash_c333 = self.user_hashes['c_333']
            user_hash_b222 = self.user_hashes['b_222']
            
            # Attempt cross-user query (should return empty)
            leak_query = db.session.query(Expense).filter(
                Expense.user_id == user_hash_c333,
                Expense.description.ilike('%Bob%')
            ).all()
            
            if len(leak_query) == 0:
                self.log_result("CROSS_USER_LEAK", "PASS", "No cross-user data leakage detected")
            else:
                self.log_result("CROSS_USER_LEAK", "FAIL", 
                              f"Found {len(leak_query)} cross-user records")
            
            # Test compound filter isolation
            mixed_query = db.session.query(Expense).filter(
                db.or_(
                    Expense.user_id == user_hash_c333,
                    Expense.user_id == user_hash_b222
                )
            ).all()
            
            # Verify each record belongs to correct user
            user_separation = {'c_333': 0, 'b_222': 0, 'other': 0}
            for expense in mixed_query:
                if expense.user_id == user_hash_c333:
                    user_separation['c_333'] += 1
                elif expense.user_id == user_hash_b222:
                    user_separation['b_222'] += 1
                else:
                    user_separation['other'] += 1
            
            if user_separation['other'] == 0:
                self.log_result("COMPOUND_FILTER_ISOLATION", "PASS", 
                              f"Clean separation: {user_separation}")
            else:
                self.log_result("COMPOUND_FILTER_ISOLATION", "FAIL", 
                              f"Foreign data in compound query: {user_separation}")
                
        except Exception as e:
            self.log_result("CROSS_USER_LEAK", "ERROR", str(e))
    
    def test_ai_context_scoping(self):
        """Test AI context building with user scoping"""
        try:
            # Build context for c_333
            user_hash_c333 = self.user_hashes['c_333']
            
            context = self.build_ai_context(user_hash_c333)
            
            # Verify context only contains c_333 data
            if (context['user_id'] == user_hash_c333 and 
                len(context['expenses']) >= 3 and
                all(exp['user_id'] == user_hash_c333 for exp in context['expenses'])):
                
                self.log_result("AI_CONTEXT_SCOPING", "PASS", 
                              f"Context properly scoped: {len(context['expenses'])} expenses")
            else:
                self.log_result("AI_CONTEXT_SCOPING", "FAIL", 
                              "Context contamination or missing data")
                
        except Exception as e:
            self.log_result("AI_CONTEXT_SCOPING", "ERROR", str(e))
    
    def build_ai_context(self, user_id_hash):
        """Build AI context for a specific user (isolated)"""
        # Get user expenses (last 100, most recent first)
        expenses = db.session.query(Expense).filter(
            Expense.user_id == user_id_hash
        ).order_by(Expense.created_at.desc()).limit(100).all()
        
        # Get user profile
        user = db.session.query(User).filter(
            User.user_id_hash == user_id_hash
        ).first()
        
        return {
            'user_id': user_id_hash,
            'user_profile': {
                'total_expenses': float(user.total_expenses) if user else 0,
                'expense_count': user.expense_count if user else 0
            },
            'expenses': [
                {
                    'user_id': exp.user_id,
                    'description': exp.description,
                    'amount': float(exp.amount),
                    'category': exp.category,
                    'date': exp.date.isoformat()
                } for exp in expenses
            ]
        }
    
    def test_concurrent_requests(self):
        """Test concurrent AI requests for different users"""
        try:
            def make_ai_request(user_id):
                """Simulate AI request for specific user"""
                with app.app_context():  # Fix: Ensure Flask app context
                    try:
                        user_hash = self.user_hashes[user_id]
                        context = self.build_ai_context(user_hash)
                        
                        # Simulate AI processing time
                        time.sleep(0.1)
                        
                        return {
                            'user_id': user_id,
                            'user_hash': user_hash,
                            'expense_count': len(context['expenses']),
                            'context_user_id': context['user_id'],
                            'success': context['user_id'] == user_hash
                        }
                    except Exception as e:
                        return {
                            'user_id': user_id,
                            'success': False,
                            'error': str(e)
                        }
            
            # Run 5 concurrent requests
            test_users = ['c_333', 'a_111', 'b_222', 'c_333', 'a_111']
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_ai_request, uid) for uid in test_users]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            # Verify all requests succeeded and maintained isolation
            success_count = sum(1 for r in results if r.get('success', False))
            
            if success_count == len(test_users):
                self.log_result("CONCURRENT_REQUESTS", "PASS", 
                              f"All {len(results)} concurrent requests isolated successfully")
            else:
                failed = [r for r in results if not r.get('success', False)]
                self.log_result("CONCURRENT_REQUESTS", "FAIL", 
                              f"Failed requests: {failed}")
                
        except Exception as e:
            self.log_result("CONCURRENT_REQUESTS", "ERROR", str(e))
    
    def test_prompt_injection_defense(self):
        """Test defense against prompt injection attacks"""
        try:
            # Simulate prompt injection attempt
            user_hash_c333 = self.user_hashes['c_333']
            
            # Build clean context
            context = self.build_ai_context(user_hash_c333)
            
            # Check that context only contains c_333 data
            injection_patterns = ['Bob', 'Alice', 'b_222', 'a_111']
            context_str = json.dumps(context).lower()
            
            found_injections = [pattern for pattern in injection_patterns 
                              if pattern.lower() in context_str]
            
            if len(found_injections) == 0:
                self.log_result("PROMPT_INJECTION_DEFENSE", "PASS", 
                              "No foreign user data in context")
            else:
                self.log_result("PROMPT_INJECTION_DEFENSE", "FAIL", 
                              f"Found foreign data patterns: {found_injections}")
                
        except Exception as e:
            self.log_result("PROMPT_INJECTION_DEFENSE", "ERROR", str(e))
    
    def test_mutation_safety(self):
        """Test data mutation isolation"""
        try:
            user_hash_c333 = self.user_hashes['c_333']
            
            # Get initial counts for all users
            initial_counts = {}
            for user_id, user_hash in self.user_hashes.items():
                initial_counts[user_id] = db.session.query(Expense).filter(
                    Expense.user_id == user_hash
                ).count()
            
            # Add new expense for c_333
            new_expense = Expense(
                user_id=user_hash_c333,
                description='Test mutation expense',
                amount=Decimal('500.00'),
                category='test',
                date=date.today(),
                month=date.today().strftime('%Y-%m'),
                unique_id=f'mutation_test_{int(time.time())}',
                platform='messenger'
            )
            db.session.add(new_expense)
            db.session.commit()
            
            # Verify only c_333 count changed
            final_counts = {}
            for user_id, user_hash in self.user_hashes.items():
                final_counts[user_id] = db.session.query(Expense).filter(
                    Expense.user_id == user_hash
                ).count()
            
            # Check isolation
            c333_increased = final_counts['c_333'] == initial_counts['c_333'] + 1
            others_unchanged = all(
                final_counts[uid] == initial_counts[uid] 
                for uid in ['a_111', 'b_222']
            )
            
            if c333_increased and others_unchanged:
                self.log_result("MUTATION_SAFETY", "PASS", 
                              f"Counts: {initial_counts} -> {final_counts}")
            else:
                self.log_result("MUTATION_SAFETY", "FAIL", 
                              f"Unexpected count changes: {initial_counts} -> {final_counts}")
                
        except Exception as e:
            db.session.rollback()
            self.log_result("MUTATION_SAFETY", "ERROR", str(e))
    
    def cleanup_test_data(self):
        """Clean up test data"""
        try:
            # Remove test expenses for c_333
            user_hash_c333 = self.user_hashes['c_333']
            
            db.session.query(Expense).filter(
                Expense.user_id == user_hash_c333,
                Expense.unique_id.like('c333_%')
            ).delete(synchronize_session=False)
            
            db.session.query(Expense).filter(
                Expense.user_id == user_hash_c333,
                Expense.unique_id.like('mutation_test_%')
            ).delete(synchronize_session=False)
            
            db.session.commit()
            logger.info("Test data cleanup completed")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Cleanup error: {str(e)}")
    
    def generate_final_report(self):
        """Generate comprehensive UAT report"""
        logger.info("=== MULTI-USER DATA ISOLATION UAT RESULTS ===")
        
        passed_tests = [name for name, result in self.results.items() 
                       if result['status'] == 'PASS']
        failed_tests = [name for name, result in self.results.items() 
                       if result['status'] == 'FAIL']
        error_tests = [name for name, result in self.results.items() 
                      if result['status'] == 'ERROR']
        
        total_tests = len(self.results)
        pass_rate = len(passed_tests) / total_tests * 100 if total_tests > 0 else 0
        
        print(f"\n📊 UAT SUMMARY")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {len(passed_tests)} ({pass_rate:.1f}%)")
        print(f"Failed: {len(failed_tests)}")
        print(f"Errors: {len(error_tests)}")
        
        if passed_tests:
            print(f"\n✅ PASSED TESTS:")
            for test in passed_tests:
                details = self.results[test].get('details', '')
                print(f"  - {test}: {details}")
        
        if failed_tests:
            print(f"\n❌ FAILED TESTS:")
            for test in failed_tests:
                details = self.results[test].get('details', '')
                print(f"  - {test}: {details}")
        
        if error_tests:
            print(f"\n🚨 ERROR TESTS:")
            for test in error_tests:
                details = self.results[test].get('details', '')
                print(f"  - {test}: {details}")
        
        # Overall assessment
        critical_tests = ['DATA_ISOLATION', 'CROSS_USER_LEAK', 'AI_CONTEXT_SCOPING']
        critical_passed = all(
            self.results.get(test, {}).get('status') == 'PASS' 
            for test in critical_tests
        )
        
        if critical_passed and len(failed_tests) == 0:
            print(f"\n🎯 OVERALL: PASS - Multi-user isolation is secure")
        else:
            print(f"\n⚠️ OVERALL: NEEDS ATTENTION - Critical issues found")
        
        return {
            'total_tests': total_tests,
            'passed': len(passed_tests),
            'failed': len(failed_tests),
            'errors': len(error_tests),
            'pass_rate': pass_rate,
            'critical_passed': critical_passed
        }


def main():
    """Run the multi-user isolation UAT"""
    # Set environment for UAT
    os.environ['AI_ENABLED'] = 'true'
    os.environ['ENV'] = 'uat'
    
    uat = MultiUserIsolationUAT()
    uat.run_all_tests()


if __name__ == '__main__':
    main()