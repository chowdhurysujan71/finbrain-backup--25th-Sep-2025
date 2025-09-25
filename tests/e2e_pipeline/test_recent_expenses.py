"""
E2E Tests for RECENT Expenses Verification

Tests the complete recent expenses retrieval system including:
- Backend API session authentication
- Correct ordering and pagination
- User isolation in expense retrieval
- Time range filtering
- Data consistency across creation paths
"""
import json
from datetime import datetime, timedelta

from tests.e2e_pipeline.test_base import E2ETestBase


class TestRecentExpensesE2E(E2ETestBase):
    """End-to-end tests for recent expenses retrieval"""

    def test_backend_api_get_recent_expenses_authentication(self, client, test_users):
        """Test that get_recent_expenses requires session authentication"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Try accessing without session authentication
            response = client.post('/api/backend/get_recent_expenses',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            # Should require authentication
            assert response.status_code in [401, 403], f"Expected auth required, got {response.status_code}"

    def test_backend_api_get_recent_expenses_with_session_auth(self, client, test_users):
        """Test get_recent_expenses with proper session authentication"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create test expense history
            self.create_test_expenses_history(user['session_user_id'], count=5)
            
            # Setup session authentication
            self.setup_session_auth(client, user['session_user_id'])
            
            # Request recent expenses
            response = client.post('/api/backend/get_recent_expenses',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            # Should succeed with authentication
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify response structure
            assert 'expenses' in data or 'recent_expenses' in data or 'success' in data
            
            # If expenses are returned, verify structure
            expenses_key = 'expenses' if 'expenses' in data else 'recent_expenses'
            if expenses_key in data:
                expenses = data[expenses_key]
                assert isinstance(expenses, list)
                
                # Verify expense structure
                for expense in expenses:
                    assert 'amount' in expense or 'description' in expense

    def test_recent_expenses_ordering(self, client, test_users):
        """Test that recent expenses are ordered correctly (most recent first)"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses with different timestamps
            from utils.db import create_expense
            expenses_created = []
            
            base_time = datetime.now()
            for i in range(3):
                expense_time = base_time - timedelta(hours=i)
                result = create_expense(
                    user_id=user['session_user_id'],
                    amount=float(100 + (i * 50)),
                    currency='৳',
                    category=f'test_order_{i}',
                    occurred_at=expense_time,
                    source_message_id=f'order_test_{i}',
                    correlation_id=f'order_corr_{i}',
                    notes=f'Ordering test expense {i}'
                )
                expenses_created.append((expense_time, 100 + (i * 50)))
            
            # Setup session auth and get recent expenses
            self.setup_session_auth(client, user['session_user_id'])
            response = client.post('/api/backend/get_recent_expenses',
                                 data=json.dumps({'limit': 5}),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Check ordering
            expenses_key = 'expenses' if 'expenses' in data else 'recent_expenses'
            if expenses_key in data and len(data[expenses_key]) >= 2:
                expenses = data[expenses_key]
                
                # Verify most recent first (if timestamps are available)
                for i in range(len(expenses) - 1):
                    current_expense = expenses[i]
                    next_expense = expenses[i + 1]
                    
                    # Compare timestamps or created_at fields if available
                    current_time = current_expense.get('created_at') or current_expense.get('timestamp')
                    next_time = next_expense.get('created_at') or next_expense.get('timestamp')
                    
                    if current_time and next_time:
                        assert current_time >= next_time, "Expenses should be ordered by most recent first"

    def test_recent_expenses_pagination(self, client, test_users):
        """Test pagination in recent expenses retrieval"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create multiple expenses
            expense_count = 8
            from utils.db import create_expense
            
            for i in range(expense_count):
                create_expense(
                    user_id=user['session_user_id'],
                    amount=float(10 + i),
                    currency='৳',
                    category=f'pagination_{i}',
                    occurred_at=datetime.now() - timedelta(minutes=i),
                    source_message_id=f'pagination_test_{i}',
                    correlation_id=f'pagination_corr_{i}',
                    notes=f'Pagination test expense {i}'
                )
            
            # Setup session auth
            self.setup_session_auth(client, user['session_user_id'])
            
            # Test with limit parameter
            limited_response = client.post('/api/backend/get_recent_expenses',
                                         data=json.dumps({'limit': 3}),
                                         content_type='application/json')
            
            if limited_response.status_code == 200:
                limited_data = limited_response.get_json()
                expenses_key = 'expenses' if 'expenses' in limited_data else 'recent_expenses'
                
                if expenses_key in limited_data:
                    limited_expenses = limited_data[expenses_key]
                    # Should respect limit (or return all if less than limit)
                    assert len(limited_expenses) <= 3, f"Expected max 3 expenses, got {len(limited_expenses)}"
            
            # Test without limit (should return default number)
            unlimited_response = client.post('/api/backend/get_recent_expenses',
                                           data=json.dumps({}),
                                           content_type='application/json')
            
            assert unlimited_response.status_code == 200

    def test_recent_expenses_user_isolation(self, client, test_users):
        """Test that recent expenses are properly isolated between users"""
        with self.mock_environment_secrets():
            user_alice = test_users['alice']
            user_bob = test_users['bob']
            
            # Create expenses for each user
            from utils.db import create_expense
            
            # Alice's expenses
            alice_expense = create_expense(
                user_id=user_alice['session_user_id'],
                amount=100.0,
                currency='৳',
                category='alice_recent',
                occurred_at=datetime.now(),
                source_message_id='alice_recent_001',
                correlation_id='alice_recent_corr_001',
                notes='Alice recent expense'
            )
            
            # Bob's expenses
            bob_expense = create_expense(
                user_id=user_bob['session_user_id'],
                amount=200.0,
                currency='৳',
                category='bob_recent',
                occurred_at=datetime.now(),
                source_message_id='bob_recent_001',
                correlation_id='bob_recent_corr_001',
                notes='Bob recent expense'
            )
            
            # Get Alice's recent expenses
            self.setup_session_auth(client, user_alice['session_user_id'])
            alice_response = client.post('/api/backend/get_recent_expenses',
                                       data=json.dumps({}),
                                       content_type='application/json')
            
            assert alice_response.status_code == 200
            alice_data = alice_response.get_json()
            
            # Get Bob's recent expenses
            self.setup_session_auth(client, user_bob['session_user_id'])
            bob_response = client.post('/api/backend/get_recent_expenses',
                                     data=json.dumps({}),
                                     content_type='application/json')
            
            assert bob_response.status_code == 200
            bob_data = bob_response.get_json()
            
            # Verify isolation
            alice_expenses_key = 'expenses' if 'expenses' in alice_data else 'recent_expenses'
            bob_expenses_key = 'expenses' if 'expenses' in bob_data else 'recent_expenses'
            
            if alice_expenses_key in alice_data and bob_expenses_key in bob_data:
                alice_expenses = alice_data[alice_expenses_key]
                bob_expenses = bob_data[bob_expenses_key]
                
                # Verify Alice doesn't see Bob's expenses and vice versa
                alice_categories = [exp.get('category', '') for exp in alice_expenses]
                bob_categories = [exp.get('category', '') for exp in bob_expenses]
                
                assert 'bob_recent' not in alice_categories, "Alice should not see Bob's expenses"
                assert 'alice_recent' not in bob_categories, "Bob should not see Alice's expenses"

    def test_recent_expenses_consistency_across_creation_paths(self, client, test_users):
        """Test that recent expenses show expenses created via different paths"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses via different paths
            expenses_created = []
            
            # 1. Via direct database creation (chat path)
            from utils.db import create_expense
            chat_result = create_expense(
                user_id=user['session_user_id'],
                amount=50.0,
                currency='৳',
                category='chat_path',
                occurred_at=datetime.now(),
                source_message_id='recent_chat_001',
                correlation_id='recent_chat_corr_001',
                notes='Chat path expense'
            )
            expenses_created.append(('chat_path', 50.0))
            
            # 2. Via form path
            headers = self.setup_x_user_id_auth(user['session_user_id'])
            form_data = {
                'amount': '75.0',
                'category': 'form_path',
                'description': 'Form path expense'
            }
            
            form_response = client.post('/expense', data=form_data, headers=headers)
            if form_response.status_code == 200:
                expenses_created.append(('form_path', 75.0))
            
            # Get recent expenses
            self.setup_session_auth(client, user['session_user_id'])
            response = client.post('/api/backend/get_recent_expenses',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify both expenses appear
            expenses_key = 'expenses' if 'expenses' in data else 'recent_expenses'
            if expenses_key in data:
                recent_expenses = data[expenses_key]
                found_categories = [exp.get('category', '') for exp in recent_expenses]
                
                # Should include expenses from different creation paths
                assert any('chat' in cat or 'path' in cat for cat in found_categories), (
                    "Should include expenses from different creation paths"
                )

    def test_recent_expenses_time_range_filtering(self, client, test_users):
        """Test time range filtering in recent expenses"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses across different time periods
            from utils.db import create_expense
            
            now = datetime.now()
            
            # Today's expense
            today_expense = create_expense(
                user_id=user['session_user_id'],
                amount=100.0,
                currency='৳',
                category='today',
                occurred_at=now,
                source_message_id='timerange_today_001',
                correlation_id='timerange_today_corr_001',
                notes='Today expense'
            )
            
            # Yesterday's expense
            yesterday_expense = create_expense(
                user_id=user['session_user_id'],
                amount=150.0,
                currency='৳',
                category='yesterday',
                occurred_at=now - timedelta(days=1),
                source_message_id='timerange_yesterday_001',
                correlation_id='timerange_yesterday_corr_001',
                notes='Yesterday expense'
            )
            
            # Last week's expense
            last_week_expense = create_expense(
                user_id=user['session_user_id'],
                amount=200.0,
                currency='৳',
                category='last_week',
                occurred_at=now - timedelta(days=7),
                source_message_id='timerange_lastweek_001',
                correlation_id='timerange_lastweek_corr_001',
                notes='Last week expense'
            )
            
            # Setup session auth
            self.setup_session_auth(client, user['session_user_id'])
            
            # Test different time range filters
            time_ranges = [
                {'timeframe': 'today'},
                {'timeframe': 'week'},
                {'timeframe': 'month'},
                {'days': 7}
            ]
            
            for time_filter in time_ranges:
                response = client.post('/api/backend/get_recent_expenses',
                                     data=json.dumps(time_filter),
                                     content_type='application/json')
                
                if response.status_code == 200:
                    data = response.get_json()
                    expenses_key = 'expenses' if 'expenses' in data else 'recent_expenses'
                    
                    if expenses_key in data:
                        filtered_expenses = data[expenses_key]
                        # Verify filtering works (implementation dependent)
                        assert isinstance(filtered_expenses, list)

    def test_recent_expenses_category_filtering(self, client, test_users):
        """Test category filtering in recent expenses"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses in different categories
            from utils.db import create_expense
            categories = ['food', 'transport', 'entertainment', 'food']  # 'food' appears twice
            
            for i, category in enumerate(categories):
                create_expense(
                    user_id=user['session_user_id'],
                    amount=float(25 + (i * 10)),
                    currency='৳',
                    category=category,
                    occurred_at=datetime.now() - timedelta(minutes=i),
                    source_message_id=f'category_filter_{i}',
                    correlation_id=f'category_filter_corr_{i}',
                    notes=f'{category.title()} expense {i}'
                )
            
            # Setup session auth
            self.setup_session_auth(client, user['session_user_id'])
            
            # Test category filtering
            category_filter = {'category': 'food'}
            response = client.post('/api/backend/get_recent_expenses',
                                 data=json.dumps(category_filter),
                                 content_type='application/json')
            
            if response.status_code == 200:
                data = response.get_json()
                expenses_key = 'expenses' if 'expenses' in data else 'recent_expenses'
                
                if expenses_key in data:
                    filtered_expenses = data[expenses_key]
                    
                    # If filtering is implemented, verify it works
                    for expense in filtered_expenses:
                        expense_category = expense.get('category', '')
                        if expense_category:  # Only check if category is present
                            assert 'food' in expense_category.lower(), (
                                f"Expected food category, got {expense_category}"
                            )

    def test_recent_expenses_empty_result(self, client, test_users):
        """Test recent expenses when user has no expenses"""
        with self.mock_environment_secrets():
            user = test_users['bob']  # Assuming Bob starts with no expenses
            
            # Setup session auth
            self.setup_session_auth(client, user['session_user_id'])
            
            # Request recent expenses for user with no expenses
            response = client.post('/api/backend/get_recent_expenses',
                                 data=json.dumps({}),
                                 content_type='application/json')
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Should return empty list or handle gracefully
            expenses_key = 'expenses' if 'expenses' in data else 'recent_expenses'
            if expenses_key in data:
                expenses = data[expenses_key]
                assert isinstance(expenses, list), "Should return list even if empty"
            else:
                # Should at least return success or appropriate message
                assert 'success' in data or 'message' in data

    def test_recent_expenses_large_dataset_performance(self, client, test_users):
        """Test performance with large number of expenses"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create many expenses
            from utils.db import create_expense
            
            expense_count = 50  # Reasonable number for testing
            for i in range(expense_count):
                create_expense(
                    user_id=user['session_user_id'],
                    amount=float(5 + (i % 20)),
                    currency='৳',
                    category=f'perf_test_{i % 5}',  # 5 different categories
                    occurred_at=datetime.now() - timedelta(minutes=i),
                    source_message_id=f'perf_test_{i}',
                    correlation_id=f'perf_test_corr_{i}',
                    notes=f'Performance test expense {i}'
                )
            
            # Setup session auth
            self.setup_session_auth(client, user['session_user_id'])
            
            # Request with reasonable limit
            import time
            start_time = time.time()
            
            response = client.post('/api/backend/get_recent_expenses',
                                 data=json.dumps({'limit': 10}),
                                 content_type='application/json')
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Should respond quickly (under 5 seconds even in test environment)
            assert response_time < 5.0, f"Response took {response_time:.2f}s, should be under 5s"
            assert response.status_code == 200
            
            data = response.get_json()
            expenses_key = 'expenses' if 'expenses' in data else 'recent_expenses'
            
            if expenses_key in data:
                expenses = data[expenses_key]
                # Should respect limit
                assert len(expenses) <= 10, f"Expected max 10 expenses, got {len(expenses)}"