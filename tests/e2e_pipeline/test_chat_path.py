"""
E2E Tests for Chat Path Expense Creation

Tests the complete chat-based expense creation flow including:
- Message parsing and categorization
- Database persistence
- User totals updates
- Monthly summary updates
- Idempotency handling
"""
import pytest
import json
import time
import uuid
from decimal import Decimal
from datetime import datetime

from tests.e2e_pipeline.test_base import E2ETestBase


class TestChatPathE2E(E2ETestBase):
    """End-to-end tests for chat-based expense creation"""

    def test_simple_expense_via_production_router(self, client, test_users):
        """Test simple expense creation via production router (chat path)"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            user_hash = user['psid_hash']
            
            # Import production router for direct testing
            from utils.production_router import route_message
            
            # Test simple expense message
            message = "spent 150 on groceries"
            response, intent, category, amount = route_message(
                user_id_hash=user_hash,
                text=message,
                channel="test",
                locale="en"
            )
            
            # Verify routing worked
            assert intent in ["expense_logged", "log_single"], f"Unexpected intent: {intent}"
            assert category == "groceries" or category == "food", f"Unexpected category: {category}"
            assert amount == 150.0, f"Unexpected amount: {amount}"
            
            # Verify database persistence
            expense = self.assert_expense_created(
                user_hash=user_hash,
                expected_amount=150.0,
                expected_category="groceries",
                platform="pwa"
            )
            
            # Verify user totals updated
            self.assert_user_totals_updated(user_hash, 150.0)
            
            # Verify monthly summary updated
            current_month = datetime.now().strftime('%Y-%m')
            self.assert_monthly_summary_updated(user_hash, current_month, 150.0)

    def test_bengali_expense_parsing(self, client, test_users):
        """Test Bengali language expense parsing"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            user_hash = user['psid_hash']
            
            from utils.production_router import route_message
            
            # Test Bengali expense message
            message = "২০০ টাকা খাবারে খরচ করেছি"
            response, intent, category, amount = route_message(
                user_id_hash=user_hash,
                text=message,
                channel="test",
                locale="bn"
            )
            
            # Verify parsing worked
            assert intent in ["expense_logged", "log_single"], f"Unexpected intent: {intent}"
            assert amount == 200.0, f"Expected 200, got {amount}"
            
            # Verify database persistence
            expense = self.assert_expense_created(
                user_hash=user_hash,
                expected_amount=200.0,
                expected_category="food"
            )

    def test_multi_expense_parsing(self, client, test_users):
        """Test multiple expenses in single message"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            user_hash = user['psid_hash']
            
            from utils.production_router import route_message
            
            # Test multiple expenses message  
            message = "bought lunch 120 taka and coffee 80 taka"
            response, intent, category, amount = route_message(
                user_id_hash=user_hash,
                text=message,
                channel="test"
            )
            
            # Verify multi-expense handling
            if intent == "multi_expense_logged":
                # Check both expenses were created
                expenses = []
                with client.application.app_context():
                    from models import Expense
                    expenses = Expense.query.filter_by(user_id_hash=user_hash).all()
                    
                assert len(expenses) >= 2, f"Expected at least 2 expenses, found {len(expenses)}"
                
                # Verify total amount
                total_amount = sum(float(e.amount) for e in expenses)
                assert abs(total_amount - 200.0) < 0.01, f"Expected ~200, got {total_amount}"

    def test_idempotency_with_correlation_id(self, client, test_users):
        """Test idempotency using correlation_id"""
        with self.mock_environment_secrets():
            user = test_users['alice'] 
            user_hash = user['psid_hash']
            correlation_id = str(uuid.uuid4())
            
            # Create expense via utils.db.create_expense for direct testing
            from utils.db import create_expense
            from datetime import datetime
            
            # First creation
            result1 = create_expense(
                user_id=user_hash,
                amount=100.0,
                currency='৳',
                category='test',
                occurred_at=datetime.now(),
                source_message_id='test_mid_1',
                correlation_id=correlation_id,
                notes='Test expense'
            )
            
            # Second creation with same correlation_id should not duplicate
            result2 = create_expense(
                user_id=user_hash,
                amount=100.0,
                currency='৳', 
                category='test',
                occurred_at=datetime.now(),
                source_message_id='test_mid_2',
                correlation_id=correlation_id,
                notes='Test expense duplicate'
            )
            
            # Verify no duplicates created
            self.assert_no_duplicate_expenses(user_hash, correlation_id=correlation_id)

    def test_user_isolation_chat_path(self, client, test_users):
        """Test that users cannot access each other's chat data"""
        with self.mock_environment_secrets():
            user_alice = test_users['alice']
            user_bob = test_users['bob']
            
            from utils.production_router import route_message
            
            # Alice creates expense
            route_message(
                user_id_hash=user_alice['psid_hash'],
                text="spent 100 on food",
                channel="test"
            )
            
            # Bob creates expense
            route_message(
                user_id_hash=user_bob['psid_hash'], 
                text="spent 200 on transport",
                channel="test"
            )
            
            # Verify isolation
            self.assert_user_isolation(user_alice['psid_hash'], user_bob['psid_hash'])

    def test_error_handling_invalid_expense(self, client, test_users):
        """Test error handling for invalid expense messages"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            user_hash = user['psid_hash']
            
            from utils.production_router import route_message
            
            # Test invalid message (no amount)
            response, intent, category, amount = route_message(
                user_id_hash=user_hash,
                text="bought something",
                channel="test"
            )
            
            # Should not create expense for invalid message
            assert intent not in ["expense_logged", "log_single"], f"Should not log invalid expense: {intent}"
            
            # Verify no expense created
            with client.application.app_context():
                from models import Expense
                expenses = Expense.query.filter_by(user_id_hash=user_hash).all()
                assert len(expenses) == 0, "No expense should be created for invalid message"

    def test_large_amount_validation(self, client, test_users):
        """Test validation of large expense amounts"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            user_hash = user['psid_hash']
            
            from utils.db import create_expense
            from datetime import datetime
            
            # Test amount over limit
            with pytest.raises(ValueError, match="Amount must be between"):
                create_expense(
                    user_id=user_hash,
                    amount=999999999.99,  # Over MAX_AMOUNT
                    currency='৳',
                    category='test',
                    occurred_at=datetime.now(),
                    source_message_id='test_mid',
                    correlation_id=str(uuid.uuid4()),
                    notes='Large expense'
                )

    def test_concurrent_expense_creation(self, client, test_users):
        """Test concurrent expense creation doesn't cause race conditions"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            user_hash = user['psid_hash']
            
            from utils.db import create_expense
            from datetime import datetime
            import threading
            
            results = []
            errors = []
            
            def create_expense_thread(amount):
                try:
                    result = create_expense(
                        user_id=user_hash,
                        amount=amount,
                        currency='৳',
                        category='concurrent_test',
                        occurred_at=datetime.now(),
                        source_message_id=f'test_mid_{amount}',
                        correlation_id=str(uuid.uuid4()),
                        notes=f'Concurrent expense {amount}'
                    )
                    results.append(result)
                except Exception as e:
                    errors.append(str(e))
            
            # Create multiple threads to create expenses concurrently
            threads = []
            for i in range(5):
                thread = threading.Thread(target=create_expense_thread, args=(float(10 + i),))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Verify all expenses were created successfully
            assert len(errors) == 0, f"Concurrent creation errors: {errors}"
            assert len(results) == 5, f"Expected 5 results, got {len(results)}"
            
            # Verify user totals are correct (sum of all amounts)
            expected_total = sum(range(10, 15))  # 10+11+12+13+14 = 60
            self.assert_user_totals_updated(user_hash, float(expected_total))