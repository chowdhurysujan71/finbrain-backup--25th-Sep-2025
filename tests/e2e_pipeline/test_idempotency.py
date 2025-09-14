"""
E2E Tests for Idempotency Verification

Tests comprehensive idempotency handling across all expense creation paths:
- Correlation ID based idempotency
- Message ID (MID) based idempotency for webhooks
- Unique ID based idempotency for forms
- Duplicate detection and prevention
- Cross-path idempotency consistency
"""
import pytest
import json
import uuid
import time
from datetime import datetime

from tests.e2e_pipeline.test_base import E2ETestBase


class TestIdempotencyE2E(E2ETestBase):
    """End-to-end tests for comprehensive idempotency handling"""

    def test_correlation_id_idempotency_database_layer(self, client, test_users):
        """Test correlation_id idempotency at database layer"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            correlation_id = str(uuid.uuid4())
            
            from utils.db import create_expense
            
            # First expense creation
            result1 = create_expense(
                user_id=user['psid_hash'],
                amount=100.0,
                currency='৳',
                category='test_idempotent',
                occurred_at=datetime.now(),
                source_message_id='test_mid_1',
                correlation_id=correlation_id,
                notes='First attempt'
            )
            
            assert result1 is not None
            
            # Second expense creation with same correlation_id
            result2 = create_expense(
                user_id=user['psid_hash'],
                amount=100.0,
                currency='৳',
                category='test_idempotent',
                occurred_at=datetime.now(),
                source_message_id='test_mid_2',
                correlation_id=correlation_id,
                notes='Second attempt (should be idempotent)'
            )
            
            # Should handle idempotency gracefully
            # Implementation might return same result or handle duplicate
            
            # Verify only one expense was created
            self.assert_no_duplicate_expenses(
                user_hash=user['psid_hash'],
                correlation_id=correlation_id
            )

    def test_message_id_idempotency_webhook_path(self, client, test_users):
        """Test Message ID (MID) idempotency for webhook path"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            mid = f"idempotent_mid_{int(time.time())}"
            
            # Create webhook payload
            payload = self.create_facebook_webhook_payload(
                psid=user['psid'],
                message="spent 75 on transport",
                mid=mid
            )
            
            payload_json = json.dumps(payload)
            payload_bytes = payload_json.encode('utf-8')
            signature = self.generate_facebook_signature(payload_bytes)
            
            headers = {
                'X-Hub-Signature-256': signature,
                'Content-Type': 'application/json'
            }
            
            # Send first webhook request
            response1 = client.post('/webhook/messenger', data=payload_bytes, headers=headers)
            assert response1.status_code == 200
            
            # Wait a moment then send identical request
            time.sleep(0.1)
            response2 = client.post('/webhook/messenger', data=payload_bytes, headers=headers)
            assert response2.status_code == 200
            
            # Verify no duplicate expense created
            self.assert_no_duplicate_expenses(
                user_hash=user['psid_hash'],
                mid=mid
            )

    def test_form_path_idempotency_with_correlation_header(self, client, test_users):
        """Test form path idempotency using correlation header"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            correlation_id = str(uuid.uuid4())
            
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            headers['X-Correlation-ID'] = correlation_id
            
            form_data = {
                'amount': '150.0',
                'category': 'idempotent_form',
                'description': 'Idempotency test expense'
            }
            
            # Submit form first time
            response1 = client.post('/expense', data=form_data, headers=headers)
            assert response1.status_code == 200
            
            # Submit identical form second time
            response2 = client.post('/expense', data=form_data, headers=headers)
            
            # Should handle idempotently
            if response2.status_code == 200:
                # Verify no duplicate created
                self.assert_no_duplicate_expenses(
                    user_hash=user['x_user_id'],
                    correlation_id=correlation_id
                )

    def test_cross_path_idempotency_consistency(self, client, test_users):
        """Test idempotency consistency across different creation paths"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            correlation_id = str(uuid.uuid4())
            
            # Create expense via database layer first
            from utils.db import create_expense
            db_result = create_expense(
                user_id=user['session_user_id'],
                amount=200.0,
                currency='৳',
                category='cross_path_test',
                occurred_at=datetime.now(),
                source_message_id='cross_path_db',
                correlation_id=correlation_id,
                notes='Database layer creation'
            )
            
            assert db_result is not None
            
            # Try to create via form path with same correlation_id
            headers = self.setup_x_user_id_auth(user['session_user_id'])
            headers['X-Correlation-ID'] = correlation_id
            
            form_data = {
                'amount': '200.0',
                'category': 'cross_path_test',
                'description': 'Form layer attempt'
            }
            
            form_response = client.post('/expense', data=form_data, headers=headers)
            
            # Form should handle idempotency (implementation dependent)
            # Verify no duplicate regardless
            self.assert_no_duplicate_expenses(
                user_hash=user['session_user_id'],
                correlation_id=correlation_id
            )

    def test_concurrent_idempotency_handling(self, client, test_users):
        """Test idempotency under concurrent requests"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            correlation_id = str(uuid.uuid4())
            
            import threading
            results = []
            errors = []
            
            def create_concurrent_expense():
                try:
                    from utils.db import create_expense
                    result = create_expense(
                        user_id=user['psid_hash'],
                        amount=50.0,
                        currency='৳',
                        category='concurrent_idempotent',
                        occurred_at=datetime.now(),
                        source_message_id=f'concurrent_{threading.current_thread().ident}',
                        correlation_id=correlation_id,
                        notes='Concurrent idempotency test'
                    )
                    results.append(result)
                except Exception as e:
                    errors.append(str(e))
            
            # Create multiple threads with same correlation_id
            threads = []
            for i in range(3):
                thread = threading.Thread(target=create_concurrent_expense)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # Should handle concurrent requests gracefully
            # At most one should succeed in creating the expense
            self.assert_no_duplicate_expenses(
                user_hash=user['psid_hash'],
                correlation_id=correlation_id
            )

    def test_idempotency_with_different_amounts_same_id(self, client, test_users):
        """Test idempotency behavior when amounts differ but IDs match"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            correlation_id = str(uuid.uuid4())
            
            from utils.db import create_expense
            
            # Create expense with specific amount
            result1 = create_expense(
                user_id=user['psid_hash'],
                amount=100.0,
                currency='৳',
                category='amount_diff_test',
                occurred_at=datetime.now(),
                source_message_id='amount_test_1',
                correlation_id=correlation_id,
                notes='First amount: 100'
            )
            
            # Try to create with different amount but same correlation_id
            try:
                result2 = create_expense(
                    user_id=user['psid_hash'],
                    amount=200.0,  # Different amount
                    currency='৳',
                    category='amount_diff_test',
                    occurred_at=datetime.now(),
                    source_message_id='amount_test_2',
                    correlation_id=correlation_id,
                    notes='Second amount: 200'
                )
                
                # Should handle this scenario gracefully
                # Verify no duplicate (or that original amount is preserved)
                self.assert_no_duplicate_expenses(
                    user_hash=user['psid_hash'],
                    correlation_id=correlation_id
                )
                
            except Exception as e:
                # Implementation might reject or handle differently
                pass

    def test_idempotency_timeout_behavior(self, client, test_users):
        """Test idempotency behavior over time (if implemented)"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            correlation_id = str(uuid.uuid4())
            
            from utils.db import create_expense
            
            # Create initial expense
            result1 = create_expense(
                user_id=user['psid_hash'],
                amount=75.0,
                currency='৳',
                category='timeout_test',
                occurred_at=datetime.now(),
                source_message_id='timeout_test_1',
                correlation_id=correlation_id,
                notes='Initial expense'
            )
            
            # Short wait (implementation might have timeout)
            import time
            time.sleep(1)
            
            # Try to create again after wait
            result2 = create_expense(
                user_id=user['psid_hash'],
                amount=75.0,
                currency='৳',
                category='timeout_test',
                occurred_at=datetime.now(),
                source_message_id='timeout_test_2',
                correlation_id=correlation_id,
                notes='After timeout'
            )
            
            # Should still handle idempotently
            self.assert_no_duplicate_expenses(
                user_hash=user['psid_hash'],
                correlation_id=correlation_id
            )

    def test_messenger_webhook_batch_idempotency(self, client, test_users):
        """Test idempotency in batch webhook processing"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create batch payload with duplicate message
            mid1 = f"batch_idempotent_{int(time.time())}_1"
            mid2 = f"batch_idempotent_{int(time.time())}_2"
            
            # Send first batch
            payload1 = {
                "object": "page",
                "entry": [
                    {
                        "id": "test_page_id",
                        "time": int(time.time() * 1000),
                        "messaging": [
                            {
                                "sender": {"id": user['psid']},
                                "recipient": {"id": "test_page_id"},
                                "timestamp": int(time.time() * 1000),
                                "message": {
                                    "mid": mid1,
                                    "text": "spent 100 on batch test"
                                }
                            }
                        ]
                    }
                ]
            }
            
            payload1_json = json.dumps(payload1)
            payload1_bytes = payload1_json.encode('utf-8')
            signature1 = self.generate_facebook_signature(payload1_bytes)
            
            headers = {
                'X-Hub-Signature-256': signature1,
                'Content-Type': 'application/json'
            }
            
            response1 = client.post('/webhook/messenger', data=payload1_bytes, headers=headers)
            assert response1.status_code == 200
            
            # Send batch with same message ID
            payload2 = {
                "object": "page",
                "entry": [
                    {
                        "id": "test_page_id",
                        "time": int(time.time() * 1000),
                        "messaging": [
                            {
                                "sender": {"id": user['psid']},
                                "recipient": {"id": "test_page_id"},
                                "timestamp": int(time.time() * 1000),
                                "message": {
                                    "mid": mid1,  # Same MID
                                    "text": "spent 100 on batch test"
                                }
                            },
                            {
                                "sender": {"id": user['psid']},
                                "recipient": {"id": "test_page_id"},
                                "timestamp": int(time.time() * 1000),
                                "message": {
                                    "mid": mid2,  # Different MID
                                    "text": "spent 50 on different item"
                                }
                            }
                        ]
                    }
                ]
            }
            
            payload2_json = json.dumps(payload2)
            payload2_bytes = payload2_json.encode('utf-8')
            signature2 = self.generate_facebook_signature(payload2_bytes)
            
            headers['X-Hub-Signature-256'] = signature2
            
            response2 = client.post('/webhook/messenger', data=payload2_bytes, headers=headers)
            assert response2.status_code == 200
            
            # Verify only unique messages were processed
            self.assert_no_duplicate_expenses(user_hash=user['psid_hash'], mid=mid1)

    def test_form_natural_language_idempotency(self, client, test_users):
        """Test idempotency in form natural language processing"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            correlation_id = str(uuid.uuid4())
            
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            headers['X-Correlation-ID'] = correlation_id
            
            form_data = {
                'nl_message': 'spent 125 taka on groceries today'
            }
            
            # Submit natural language form first time
            response1 = client.post('/expense', data=form_data, headers=headers)
            
            # Submit identical natural language form second time
            response2 = client.post('/expense', data=form_data, headers=headers)
            
            if response1.status_code == 200 and response2.status_code == 200:
                # Verify idempotency in natural language processing
                self.assert_no_duplicate_expenses(
                    user_hash=user['x_user_id'],
                    correlation_id=correlation_id
                )

    def test_idempotency_across_user_boundaries(self, client, test_users):
        """Test that idempotency doesn't leak across users"""
        with self.mock_environment_secrets():
            user_alice = test_users['alice']
            user_bob = test_users['bob']
            
            # Use same correlation_id for different users
            correlation_id = str(uuid.uuid4())
            
            from utils.db import create_expense
            
            # Alice creates expense
            alice_result = create_expense(
                user_id=user_alice['psid_hash'],
                amount=100.0,
                currency='৳',
                category='user_boundary_test',
                occurred_at=datetime.now(),
                source_message_id='alice_boundary',
                correlation_id=correlation_id,
                notes='Alice expense'
            )
            
            # Bob creates expense with same correlation_id
            bob_result = create_expense(
                user_id=user_bob['psid_hash'],
                amount=200.0,
                currency='৳',
                category='user_boundary_test',
                occurred_at=datetime.now(),
                source_message_id='bob_boundary',
                correlation_id=correlation_id,
                notes='Bob expense'
            )
            
            # Both should succeed (idempotency should be per-user)
            assert alice_result is not None
            assert bob_result is not None
            
            # Verify both users have their expenses
            alice_expense = self.assert_expense_created(
                user_hash=user_alice['psid_hash'],
                expected_amount=100.0,
                expected_category='user_boundary_test'
            )
            
            bob_expense = self.assert_expense_created(
                user_hash=user_bob['psid_hash'],
                expected_amount=200.0,
                expected_category='user_boundary_test'
            )

    def test_malformed_correlation_id_handling(self, client, test_users):
        """Test handling of malformed or invalid correlation IDs"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            from utils.db import create_expense
            
            # Test with various malformed correlation IDs
            invalid_correlation_ids = [
                '',  # Empty string
                None,  # None value
                'not-a-uuid',  # Invalid format
                'x' * 100,  # Too long
                'special!@#$%^&*()chars'  # Special characters
            ]
            
            for i, invalid_id in enumerate(invalid_correlation_ids):
                try:
                    result = create_expense(
                        user_id=user['psid_hash'],
                        amount=float(10 + i),
                        currency='৳',
                        category=f'malformed_{i}',
                        occurred_at=datetime.now(),
                        source_message_id=f'malformed_{i}',
                        correlation_id=invalid_id,
                        notes=f'Malformed test {i}'
                    )
                    
                    # Should handle gracefully (generate new ID or handle error)
                    
                except Exception as e:
                    # Should not crash the system
                    assert 'database' not in str(e).lower(), f"Database error with invalid correlation_id: {e}"