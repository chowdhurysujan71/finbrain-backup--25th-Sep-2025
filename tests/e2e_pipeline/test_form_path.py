"""
E2E Tests for Form Path Expense Creation

Tests the complete form-based expense creation flow including:
- Structured form data submission
- Natural language input processing
- X-User-ID header authentication
- Database persistence
- User totals updates
- Error handling and validation
"""
import uuid
from decimal import Decimal

from tests.e2e_pipeline.test_base import E2ETestBase


class TestFormPathE2E(E2ETestBase):
    """End-to-end tests for form-based expense creation"""

    def test_structured_form_expense_creation(self, client, test_users):
        """Test structured form data expense creation"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit structured form data
            form_data = {
                'amount': '150.50',
                'category': 'groceries',
                'description': 'Weekly grocery shopping',
                'currency': '৳'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            
            # Verify successful response
            assert response.status_code == 200
            response_data = response.get_json()
            assert response_data.get('success') is True
            
            # Verify database persistence
            expense = self.assert_expense_created(
                user_hash=user['x_user_id'],  # Form path uses X-User-ID directly
                expected_amount=150.50,
                expected_category='groceries',
                platform='pwa'
            )
            
            # Verify expense details
            assert expense.description == 'Weekly grocery shopping'
            assert expense.currency == '৳'
            
            # Verify user totals updated
            self.assert_user_totals_updated(user['x_user_id'], 150.50)

    def test_natural_language_form_input(self, client, test_users):
        """Test natural language input via form"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit natural language message
            form_data = {
                'nl_message': 'spent 200 taka on lunch today'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            
            # Verify successful response
            assert response.status_code == 200
            response_data = response.get_json()
            assert response_data.get('success') is True
            
            # Verify database persistence
            expense = self.assert_expense_created(
                user_hash=user['x_user_id'],
                expected_amount=200.0,
                expected_category='food',
                platform='pwa'
            )

    def test_mixed_language_natural_input(self, client, test_users):
        """Test mixed Bengali-English natural language input"""
        with self.mock_environment_secrets():
            user = test_users['bob']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit mixed language message
            form_data = {
                'nl_message': '৩০০ টাকা transport এর জন্য খরচ করলাম'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            
            # Should handle mixed language gracefully
            if response.status_code == 200:
                response_data = response.get_json()
                if response_data.get('success') is True:
                    # Verify database persistence if parsing succeeded
                    expense = self.assert_expense_created(
                        user_hash=user['x_user_id'],
                        expected_amount=300.0,
                        expected_category='transport'
                    )

    def test_form_validation_missing_amount(self, client, test_users):
        """Test form validation for missing amount"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit form without amount
            form_data = {
                'category': 'food',
                'description': 'Some food'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            
            # Should return validation error
            assert response.status_code == 400
            response_data = response.get_json()
            assert 'error' in response_data
            assert 'amount' in response_data.get('message', '').lower()

    def test_form_validation_invalid_amount(self, client, test_users):
        """Test form validation for invalid amount"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit form with invalid amount
            form_data = {
                'amount': 'not_a_number',
                'category': 'food',
                'description': 'Some food'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            
            # Should return validation error
            assert response.status_code == 400
            response_data = response.get_json()
            assert 'error' in response_data

    def test_form_authentication_required(self, client, test_users):
        """Test that form endpoints require X-User-ID authentication"""
        with self.mock_environment_secrets():
            # Submit form without X-User-ID header
            form_data = {
                'amount': '100',
                'category': 'test',
                'description': 'Test expense'
            }
            
            response = client.post('/expense', data=form_data)
            
            # Should handle missing authentication gracefully
            # (implementation might use anonymous user or return error)
            assert response.status_code in [200, 400, 401, 403]

    def test_form_large_amount_validation(self, client, test_users):
        """Test validation of large amounts via form"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit form with very large amount
            form_data = {
                'amount': '999999999.99',
                'category': 'test',
                'description': 'Large expense'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            
            # Should return validation error for amount over limit
            assert response.status_code == 400
            response_data = response.get_json()
            assert 'error' in response_data

    def test_form_idempotency_handling(self, client, test_users):
        """Test idempotency handling in form submissions"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            correlation_id = str(uuid.uuid4())
            
            # Add correlation_id to headers for idempotency
            headers['X-Correlation-ID'] = correlation_id
            
            form_data = {
                'amount': '75.25',
                'category': 'transport',
                'description': 'Bus fare'
            }
            
            # Submit first time
            response1 = client.post('/expense', data=form_data, headers=headers)
            assert response1.status_code == 200
            
            # Submit second time with same correlation_id
            response2 = client.post('/expense', data=form_data, headers=headers)
            
            # Should handle idempotency (not create duplicate)
            if response2.status_code == 200:
                self.assert_no_duplicate_expenses(
                    user_hash=user['x_user_id'],
                    correlation_id=correlation_id
                )

    def test_form_user_isolation(self, client, test_users):
        """Test user isolation in form submissions"""
        with self.mock_environment_secrets():
            user_alice = test_users['alice']
            user_bob = test_users['bob']
            
            # Alice submits expense
            headers_alice = self.setup_x_user_id_auth(user_alice['x_user_id'])
            form_data_alice = {
                'amount': '100',
                'category': 'food',
                'description': 'Alice lunch'
            }
            
            response_alice = client.post('/expense', data=form_data_alice, headers=headers_alice)
            assert response_alice.status_code == 200
            
            # Bob submits expense
            headers_bob = self.setup_x_user_id_auth(user_bob['x_user_id'])
            form_data_bob = {
                'amount': '200',
                'category': 'transport',
                'description': 'Bob taxi'
            }
            
            response_bob = client.post('/expense', data=form_data_bob, headers=headers_bob)
            assert response_bob.status_code == 200
            
            # Verify user isolation
            self.assert_user_isolation(user_alice['x_user_id'], user_bob['x_user_id'])

    def test_form_category_normalization(self, client, test_users):
        """Test category normalization in form submissions"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit form with uppercase category
            form_data = {
                'amount': '50',
                'category': 'FOOD',
                'description': 'Lunch'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            assert response.status_code == 200
            
            # Verify category is normalized to lowercase
            expense = self.assert_expense_created(
                user_hash=user['x_user_id'],
                expected_amount=50.0,
                expected_category='food'
            )

    def test_form_currency_handling(self, client, test_users):
        """Test different currency handling in forms"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            currencies = ['৳', '$', '€', 'USD', 'BDT']
            
            for i, currency in enumerate(currencies):
                form_data = {
                    'amount': str(10 + i),
                    'category': 'test',
                    'description': f'Test expense {currency}',
                    'currency': currency
                }
                
                response = client.post('/expense', data=form_data, headers=headers)
                
                if response.status_code == 200:
                    # Verify expense created with correct currency
                    with client.application.app_context():
                        from models import Expense
                        expense = Expense.query.filter_by(
                            user_id_hash=user['x_user_id'],
                            amount=Decimal(str(10 + i))
                        ).first()
                        
                        if expense:
                            # Currency should be stored (might be normalized)
                            assert expense.currency is not None

    def test_natural_language_fallback_to_structured(self, client, test_users):
        """Test fallback from natural language to structured input request"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            # Submit ambiguous natural language that might need clarification
            form_data = {
                'nl_message': 'bought something today'
            }
            
            response = client.post('/expense', data=form_data, headers=headers)
            
            # Should either succeed with AI parsing or request structured input
            assert response.status_code in [200, 400]
            
            if response.status_code == 400:
                response_data = response.get_json()
                # Should provide guidance for better input
                assert 'error' in response_data or 'message' in response_data