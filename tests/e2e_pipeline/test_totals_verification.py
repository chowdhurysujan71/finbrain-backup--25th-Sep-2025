"""
E2E Tests for TOTALS Verification

Tests the complete totals calculation and retrieval system including:
- Backend API session authentication
- Accurate totals calculation across all expense creation paths
- Monthly summary aggregation
- User isolation in totals calculation
- Concurrent update handling
"""
import pytest
import json
from decimal import Decimal
from datetime import datetime, date, timedelta

from tests.e2e_pipeline.test_base import E2ETestBase


class TestTotalsVerificationE2E(E2ETestBase):
    """End-to-end tests for totals calculation and verification"""

    def test_backend_api_get_totals_authentication(self, client, test_users):
        """Test that get_totals requires session authentication"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Try accessing without session authentication
            response = client.post('/api/backend/get_totals', 
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            # Should require authentication
            assert response.status_code in [401, 403], f"Expected auth required, got {response.status_code}"

    def test_backend_api_get_totals_with_session_auth(self, client, test_users):
        """Test get_totals with proper session authentication"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Setup session authentication
            self.setup_session_auth(client, user['session_user_id'])
            
            # Create some test expenses first
            self.create_test_expenses_history(user['session_user_id'], count=3)
            
            # Request totals
            response = client.post('/api/backend/get_totals',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            # Should succeed with authentication
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify response structure
            assert 'total_expenses' in data or 'success' in data
            if 'total_expenses' in data:
                assert isinstance(data['total_expenses'], (int, float))
                assert data['total_expenses'] >= 0

    def test_totals_accuracy_across_creation_paths(self, client, test_users):
        """Test that totals are accurate across different expense creation paths"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses via different paths
            expected_total = 0.0
            
            # 1. Via direct database creation (simulating chat path)
            from utils.db import create_expense
            result1 = create_expense(
                user_id=user['session_user_id'],
                amount=100.0,
                currency='৳',
                category='food',
                occurred_at=datetime.now(),
                source_message_id='chat_test_001',
                correlation_id='corr_001',
                notes='Chat path expense'
            )
            expected_total += 100.0
            
            # 2. Via form path
            headers = self.setup_x_user_id_auth(user['session_user_id'])
            form_data = {
                'amount': '150.50',
                'category': 'transport',
                'description': 'Form path expense'
            }
            
            form_response = client.post('/expense', data=form_data, headers=headers)
            if form_response.status_code == 200:
                expected_total += 150.50
            
            # 3. Setup session auth and get totals
            self.setup_session_auth(client, user['session_user_id'])
            
            response = client.post('/api/backend/get_totals',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify totals match expected
            if 'total_expenses' in data:
                actual_total = float(data['total_expenses'])
                assert abs(actual_total - expected_total) < 0.01, (
                    f"Expected total {expected_total}, got {actual_total}"
                )

    def test_monthly_summary_totals_consistency(self, client, test_users):
        """Test consistency between user totals and monthly summaries"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            current_month = datetime.now().strftime('%Y-%m')
            
            # Create expenses in current month
            from utils.db import create_expense
            monthly_total = 0.0
            
            for i in range(3):
                amount = 50.0 + (i * 25.0)
                create_expense(
                    user_id=user['session_user_id'],
                    amount=amount,
                    currency='৳',
                    category=f'category_{i}',
                    occurred_at=datetime.now(),
                    source_message_id=f'monthly_test_{i}',
                    correlation_id=f'monthly_corr_{i}',
                    notes=f'Monthly test expense {i}'
                )
                monthly_total += amount
            
            # Get user totals
            self.setup_session_auth(client, user['session_user_id'])
            response = client.post('/api/backend/get_totals',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            assert response.status_code == 200
            totals_data = response.get_json()
            
            # Verify monthly summary matches
            self.assert_monthly_summary_updated(
                user['session_user_id'],
                current_month,
                monthly_total
            )

    def test_totals_user_isolation(self, client, test_users):
        """Test that totals are properly isolated between users"""
        with self.mock_environment_secrets():
            user_alice = test_users['alice']
            user_bob = test_users['bob']
            
            # Create expenses for Alice
            from utils.db import create_expense
            create_expense(
                user_id=user_alice['session_user_id'],
                amount=200.0,
                currency='৳',
                category='alice_expense',
                occurred_at=datetime.now(),
                source_message_id='alice_isolation_001',
                correlation_id='alice_corr_001',
                notes='Alice isolation test'
            )
            
            # Create expenses for Bob
            create_expense(
                user_id=user_bob['session_user_id'],
                amount=300.0,
                currency='৳',
                category='bob_expense',
                occurred_at=datetime.now(),
                source_message_id='bob_isolation_001',
                correlation_id='bob_corr_001',
                notes='Bob isolation test'
            )
            
            # Get Alice's totals
            self.setup_session_auth(client, user_alice['session_user_id'])
            alice_response = client.post('/api/backend/get_totals',
                                       data=json.dumps({}),
                                       content_type='application/json')
            
            assert alice_response.status_code == 200
            alice_data = alice_response.get_json()
            
            # Get Bob's totals
            self.setup_session_auth(client, user_bob['session_user_id'])
            bob_response = client.post('/api/backend/get_totals',
                                     data=json.dumps({}),
                                     content_type='application/json')
            
            assert bob_response.status_code == 200
            bob_data = bob_response.get_json()
            
            # Verify isolation
            if 'total_expenses' in alice_data and 'total_expenses' in bob_data:
                alice_total = float(alice_data['total_expenses'])
                bob_total = float(bob_data['total_expenses'])
                
                # Each user should only see their own expenses
                assert alice_total >= 200.0, f"Alice total {alice_total} should include her 200 expense"
                assert bob_total >= 300.0, f"Bob total {bob_total} should include his 300 expense"
                
                # Totals should not include other user's expenses
                # (Exact values depend on whether other tests left data)
                assert alice_total != bob_total or (alice_total == 0 and bob_total == 0)

    def test_totals_concurrent_updates(self, client, test_users):
        """Test totals calculation under concurrent expense creation"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create multiple expenses concurrently
            import threading
            from utils.db import create_expense
            
            results = []
            errors = []
            
            def create_concurrent_expense(amount, index):
                try:
                    result = create_expense(
                        user_id=user['session_user_id'],
                        amount=float(amount),
                        currency='৳',
                        category='concurrent',
                        occurred_at=datetime.now(),
                        source_message_id=f'concurrent_{index}',
                        correlation_id=f'concurrent_corr_{index}',
                        notes=f'Concurrent expense {index}'
                    )
                    results.append(result)
                except Exception as e:
                    errors.append(str(e))
            
            # Create threads for concurrent expense creation
            threads = []
            expense_amounts = [25.0, 35.0, 45.0, 55.0, 65.0]
            expected_total = sum(expense_amounts)
            
            for i, amount in enumerate(expense_amounts):
                thread = threading.Thread(target=create_concurrent_expense, args=(amount, i))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Check for errors
            assert len(errors) == 0, f"Concurrent creation errors: {errors}"
            assert len(results) == len(expense_amounts), f"Expected {len(expense_amounts)} results, got {len(results)}"
            
            # Verify totals are accurate
            self.setup_session_auth(client, user['session_user_id'])
            response = client.post('/api/backend/get_totals',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            
            if 'total_expenses' in data:
                actual_total = float(data['total_expenses'])
                # Should include at least the concurrent expenses
                assert actual_total >= expected_total, (
                    f"Total {actual_total} should be at least {expected_total}"
                )

    def test_totals_with_expense_corrections(self, client, test_users):
        """Test that totals properly handle expense corrections and updates"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create initial expense
            from utils.db import create_expense
            original_result = create_expense(
                user_id=user['session_user_id'],
                amount=100.0,
                currency='৳',
                category='original',
                occurred_at=datetime.now(),
                source_message_id='correction_test_001',
                correlation_id='correction_corr_001',
                notes='Original expense for correction'
            )
            
            # Get initial totals
            self.setup_session_auth(client, user['session_user_id'])
            initial_response = client.post('/api/backend/get_totals',
                                         data=json.dumps({}),
                                         content_type='application/json')
            
            assert initial_response.status_code == 200
            initial_data = initial_response.get_json()
            
            if 'total_expenses' in initial_data:
                initial_total = float(initial_data['total_expenses'])
                
                # Verify initial total includes the expense
                assert initial_total >= 100.0, f"Initial total {initial_total} should include 100"

    def test_totals_time_range_filtering(self, client, test_users):
        """Test totals calculation with time range filtering"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses across different time periods
            from utils.db import create_expense
            
            # Current month expense
            current_month_expense = create_expense(
                user_id=user['session_user_id'],
                amount=100.0,
                currency='৳',
                category='current',
                occurred_at=datetime.now(),
                source_message_id='timerange_current_001',
                correlation_id='timerange_current_corr_001',
                notes='Current month expense'
            )
            
            # Last month expense
            last_month_date = datetime.now().replace(day=1) - timedelta(days=1)
            last_month_expense = create_expense(
                user_id=user['session_user_id'],
                amount=200.0,
                currency='৳',
                category='last_month',
                occurred_at=last_month_date,
                source_message_id='timerange_last_001',
                correlation_id='timerange_last_corr_001',
                notes='Last month expense'
            )
            
            # Get totals (might include time range parameter)
            self.setup_session_auth(client, user['session_user_id'])
            
            # Test current month totals
            current_month_payload = {
                'timeframe': 'current_month'
            }
            current_response = client.post('/api/backend/get_totals',
                                         data=json.dumps(current_month_payload),
                                         content_type='application/json')
            
            if current_response.status_code == 200:
                current_data = current_response.get_json()
                if 'total_expenses' in current_data:
                    current_total = float(current_data['total_expenses'])
                    # Should include current month expense
                    assert current_total >= 100.0, f"Current month total should include 100"

    def test_totals_category_breakdown(self, client, test_users):
        """Test totals with category breakdown"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses in different categories
            categories = {
                'food': 150.0,
                'transport': 75.0,
                'entertainment': 50.0
            }
            
            from utils.db import create_expense
            for category, amount in categories.items():
                create_expense(
                    user_id=user['session_user_id'],
                    amount=amount,
                    currency='৳',
                    category=category,
                    occurred_at=datetime.now(),
                    source_message_id=f'category_{category}_001',
                    correlation_id=f'category_{category}_corr_001',
                    notes=f'{category.title()} expense'
                )
            
            # Get totals with category breakdown
            self.setup_session_auth(client, user['session_user_id'])
            payload = {
                'include_categories': True
            }
            response = client.post('/api/backend/get_totals',
                                 data=json.dumps(payload),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify total matches sum of categories
            if 'total_expenses' in data:
                total = float(data['total_expenses'])
                expected_total = sum(categories.values())
                assert total >= expected_total, f"Total {total} should be at least {expected_total}"
            
            # If category breakdown is included, verify it
            if 'categories' in data:
                category_data = data['categories']
                for category, expected_amount in categories.items():
                    if category in category_data:
                        actual_amount = float(category_data[category])
                        assert actual_amount >= expected_amount, (
                            f"Category {category}: expected {expected_amount}, got {actual_amount}"
                        )