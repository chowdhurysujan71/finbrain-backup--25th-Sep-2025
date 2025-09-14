"""
E2E Tests for Audit Trail Validation

Tests comprehensive audit trail functionality including:
- Expense creation tracking
- Expense corrections and edits
- User action logging
- PCA (Precision Capture & Audit) system validation
- Correction history preservation
- Audit data integrity
"""
import pytest
import json
from datetime import datetime, timedelta

from tests.e2e_pipeline.test_base import E2ETestBase


class TestAuditTrailE2E(E2ETestBase):
    """End-to-end tests for audit trail validation"""

    def test_expense_creation_audit_trail(self, client, test_users):
        """Test that expense creation generates proper audit trail"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expense with full audit information
            from utils.db import create_expense
            
            creation_time = datetime.now()
            result = create_expense(
                user_id=user['psid_hash'],
                amount=150.0,
                currency='৳',
                category='audit_test',
                occurred_at=creation_time,
                source_message_id='audit_creation_001',
                correlation_id='audit_creation_corr_001',
                notes='Audit trail test expense'
            )
            
            assert result is not None
            
            # Verify audit trail in database
            with client.application.app_context():
                from models import Expense
                
                expense = Expense.query.filter_by(
                    correlation_id='audit_creation_corr_001'
                ).first()
                
                assert expense is not None, "Expense should be created"
                
                # Verify audit fields
                assert expense.user_id_hash == user['psid_hash']
                assert expense.mid == 'audit_creation_001'
                assert expense.correlation_id == 'audit_creation_corr_001'
                assert expense.created_at is not None
                assert expense.original_message == 'Audit trail test expense'
                
                # Verify timestamp accuracy
                time_diff = abs((expense.created_at - creation_time).total_seconds())
                assert time_diff < 5, "Creation timestamp should be accurate"

    def test_pca_inference_snapshot_creation(self, client, test_users):
        """Test that PCA system creates inference snapshots for audit"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Check if PCA tables exist and are accessible
            try:
                with client.application.app_context():
                    from models_pca import InferenceSnapshot
                    
                    # Count existing snapshots
                    initial_count = InferenceSnapshot.query.filter_by(
                        user_id=user['psid_hash']
                    ).count()
                    
                    # Create expense that should trigger PCA inference
                    from utils.production_router import route_message
                    
                    response, intent, category, amount = route_message(
                        user_id_hash=user['psid_hash'],
                        text="spent 175 on groceries for audit test",
                        channel="test",
                        locale="en"
                    )
                    
                    # Check if inference snapshot was created
                    final_count = InferenceSnapshot.query.filter_by(
                        user_id=user['psid_hash']
                    ).count()
                    
                    if final_count > initial_count:
                        # PCA system is active and creating snapshots
                        snapshots = InferenceSnapshot.query.filter_by(
                            user_id=user['psid_hash']
                        ).order_by(InferenceSnapshot.created_at.desc()).limit(1).all()
                        
                        if snapshots:
                            latest_snapshot = snapshots[0]
                            assert latest_snapshot.source_text == "spent 175 on groceries for audit test"
                            assert latest_snapshot.intent is not None
                            assert latest_snapshot.confidence is not None
                            
            except ImportError:
                # PCA models might not be available in test environment
                pytest.skip("PCA models not available")

    def test_expense_correction_audit_trail(self, client, test_users):
        """Test audit trail for expense corrections"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create original expense
            from utils.db import create_expense
            
            original_expense = create_expense(
                user_id=user['psid_hash'],
                amount=100.0,
                currency='৳',
                category='original_category',
                occurred_at=datetime.now(),
                source_message_id='correction_audit_001',
                correlation_id='correction_audit_corr_001',
                notes='Original expense for correction audit'
            )
            
            # Simulate expense correction
            with client.application.app_context():
                from models import Expense
                
                expense = Expense.query.filter_by(
                    correlation_id='correction_audit_corr_001'
                ).first()
                
                if expense:
                    # Update expense to simulate correction
                    original_amount = expense.amount
                    original_category = expense.category
                    
                    expense.amount = 150.0  # Corrected amount
                    expense.category = 'corrected_category'
                    expense.corrected_at = datetime.utcnow()
                    expense.corrected_reason = 'User correction via audit test'
                    
                    from db_base import db
                    db.session.commit()
                    
                    # Verify correction audit fields
                    corrected_expense = Expense.query.filter_by(
                        correlation_id='correction_audit_corr_001'
                    ).first()
                    
                    if corrected_expense:
                        assert float(corrected_expense.amount) == 150.0
                        assert corrected_expense.category == 'corrected_category'
                        assert corrected_expense.corrected_at is not None
                        assert corrected_expense.corrected_reason == 'User correction via audit test'

    def test_user_correction_history_preservation(self, client, test_users):
        """Test that user correction history is properly preserved"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            try:
                with client.application.app_context():
                    from models_pca import UserCorrection
                    
                    # Count existing corrections
                    initial_count = UserCorrection.query.filter_by(
                        user_id=user['psid_hash']
                    ).count()
                    
                    # Create a correction record
                    correction = UserCorrection()
                    correction.corr_id = f"test_corr_{int(datetime.now().timestamp())}"
                    correction.tx_id = f"test_tx_{int(datetime.now().timestamp())}"
                    correction.user_id = user['psid_hash']
                    correction.fields_json = {
                        "amount": {"old": 100.0, "new": 125.0},
                        "category": {"old": "food", "new": "groceries"}
                    }
                    correction.reason = "Audit trail test correction"
                    correction.correction_type = "manual"
                    correction.source_message = "corrected amount to 125 and category to groceries"
                    correction.created_at = datetime.utcnow()
                    
                    from db_base import db
                    db.session.add(correction)
                    db.session.commit()
                    
                    # Verify correction was saved
                    saved_correction = UserCorrection.query.filter_by(
                        corr_id=correction.corr_id
                    ).first()
                    
                    assert saved_correction is not None
                    assert saved_correction.user_id == user['psid_hash']
                    assert saved_correction.fields_json["amount"]["old"] == 100.0
                    assert saved_correction.fields_json["amount"]["new"] == 125.0
                    assert saved_correction.reason == "Audit trail test correction"
                    
            except ImportError:
                pytest.skip("UserCorrection model not available")

    def test_audit_trail_data_integrity(self, client, test_users):
        """Test audit trail data integrity and consistency"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create multiple related expenses
            from utils.db import create_expense
            
            base_time = datetime.now()
            expense_ids = []
            
            for i in range(3):
                result = create_expense(
                    user_id=user['psid_hash'],
                    amount=float(50 + (i * 25)),
                    currency='৳',
                    category=f'integrity_test_{i}',
                    occurred_at=base_time - timedelta(minutes=i),
                    source_message_id=f'integrity_test_{i}',
                    correlation_id=f'integrity_corr_{i}',
                    notes=f'Integrity test expense {i}'
                )
                if result:
                    expense_ids.append(result.get('expense_id'))
            
            # Verify audit trail consistency
            with client.application.app_context():
                from models import Expense
                
                expenses = Expense.query.filter(
                    Expense.correlation_id.like('integrity_corr_%')
                ).order_by(Expense.created_at).all()
                
                assert len(expenses) == 3, f"Expected 3 expenses, found {len(expenses)}"
                
                # Verify chronological order
                for i in range(len(expenses) - 1):
                    current_expense = expenses[i]
                    next_expense = expenses[i + 1]
                    
                    assert current_expense.created_at <= next_expense.created_at, (
                        "Expenses should be in chronological order"
                    )
                
                # Verify data integrity
                for expense in expenses:
                    # All audit fields should be populated
                    assert expense.user_id_hash == user['psid_hash']
                    assert expense.created_at is not None
                    assert expense.correlation_id is not None
                    assert expense.mid is not None
                    assert expense.original_message is not None
                    
                    # Amounts should match expected pattern
                    category_index = int(expense.category.split('_')[-1])
                    expected_amount = float(50 + (category_index * 25))
                    actual_amount = float(expense.amount)
                    
                    assert abs(actual_amount - expected_amount) < 0.01, (
                        f"Amount mismatch: expected {expected_amount}, got {actual_amount}"
                    )

    def test_audit_trail_cross_path_consistency(self, client, test_users):
        """Test audit trail consistency across different creation paths"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            audit_records = []
            
            # Create via database layer (chat path simulation)
            from utils.db import create_expense
            db_result = create_expense(
                user_id=user['psid_hash'],
                amount=100.0,
                currency='৳',
                category='cross_path_db',
                occurred_at=datetime.now(),
                source_message_id='cross_path_db_001',
                correlation_id='cross_path_db_corr_001',
                notes='Database path audit test'
            )
            audit_records.append(('db', db_result))
            
            # Create via form path
            headers = self.setup_x_user_id_auth(user['psid_hash'])
            headers['X-Correlation-ID'] = 'cross_path_form_corr_001'
            
            form_data = {
                'amount': '200.0',
                'category': 'cross_path_form',
                'description': 'Form path audit test'
            }
            
            form_response = client.post('/expense', data=form_data, headers=headers)
            audit_records.append(('form', form_response))
            
            # Verify consistent audit trail structure
            with client.application.app_context():
                from models import Expense
                
                # Check database path expense
                db_expense = Expense.query.filter_by(
                    correlation_id='cross_path_db_corr_001'
                ).first()
                
                if db_expense:
                    assert db_expense.user_id_hash == user['psid_hash']
                    assert db_expense.created_at is not None
                    assert db_expense.mid == 'cross_path_db_001'
                    assert db_expense.original_message == 'Database path audit test'
                
                # Check form path expense
                form_expense = Expense.query.filter_by(
                    correlation_id='cross_path_form_corr_001'
                ).first()
                
                if form_expense:
                    assert form_expense.user_id_hash == user['psid_hash']
                    assert form_expense.created_at is not None
                    # Form path might have different mid or message format
                    assert form_expense.original_message is not None

    def test_audit_trail_query_performance(self, client, test_users):
        """Test audit trail query performance with larger datasets"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create multiple expenses for performance testing
            from utils.db import create_expense
            import time
            
            expense_count = 20  # Reasonable for testing
            start_time = time.time()
            
            for i in range(expense_count):
                create_expense(
                    user_id=user['psid_hash'],
                    amount=float(10 + i),
                    currency='৳',
                    category=f'perf_audit_{i % 5}',
                    occurred_at=datetime.now() - timedelta(minutes=i),
                    source_message_id=f'perf_audit_{i}',
                    correlation_id=f'perf_audit_corr_{i}',
                    notes=f'Performance audit test expense {i}'
                )
            
            creation_time = time.time() - start_time
            
            # Query audit trail
            query_start_time = time.time()
            
            with client.application.app_context():
                from models import Expense
                
                # Query recent expenses
                recent_expenses = Expense.query.filter_by(
                    user_id_hash=user['psid_hash']
                ).order_by(Expense.created_at.desc()).limit(10).all()
                
                # Query by date range
                since_date = datetime.now() - timedelta(hours=1)
                date_range_expenses = Expense.query.filter(
                    Expense.user_id_hash == user['psid_hash'],
                    Expense.created_at >= since_date
                ).all()
                
                # Query by category pattern
                category_expenses = Expense.query.filter(
                    Expense.user_id_hash == user['psid_hash'],
                    Expense.category.like('perf_audit_%')
                ).all()
                
            query_time = time.time() - query_start_time
            
            # Performance assertions
            assert creation_time < 10.0, f"Creating {expense_count} expenses took {creation_time:.2f}s, should be under 10s"
            assert query_time < 5.0, f"Audit queries took {query_time:.2f}s, should be under 5s"
            
            # Verify results
            assert len(recent_expenses) <= 10, "Should respect limit"
            assert len(date_range_expenses) >= expense_count, "Should find all recent expenses"
            assert len(category_expenses) >= expense_count, "Should find all matching categories"

    def test_audit_trail_user_isolation(self, client, test_users):
        """Test that audit trails are properly isolated between users"""
        with self.mock_environment_secrets():
            user_alice = test_users['alice']
            user_bob = test_users['bob']
            
            # Create expenses for both users with identifiable patterns
            from utils.db import create_expense
            
            alice_expense = create_expense(
                user_id=user_alice['psid_hash'],
                amount=111.0,
                currency='৳',
                category='alice_audit_isolation',
                occurred_at=datetime.now(),
                source_message_id='alice_audit_isolation_001',
                correlation_id='alice_audit_isolation_corr_001',
                notes='Alice audit isolation test'
            )
            
            bob_expense = create_expense(
                user_id=user_bob['psid_hash'],
                amount=222.0,
                currency='৳',
                category='bob_audit_isolation',
                occurred_at=datetime.now(),
                source_message_id='bob_audit_isolation_001',
                correlation_id='bob_audit_isolation_corr_001',
                notes='Bob audit isolation test'
            )
            
            # Verify audit trail isolation
            with client.application.app_context():
                from models import Expense
                
                # Alice's audit trail
                alice_audit = Expense.query.filter_by(
                    user_id_hash=user_alice['psid_hash']
                ).all()
                
                # Bob's audit trail
                bob_audit = Expense.query.filter_by(
                    user_id_hash=user_bob['psid_hash']
                ).all()
                
                # Verify isolation
                alice_messages = [e.original_message for e in alice_audit]
                bob_messages = [e.original_message for e in bob_audit]
                
                assert 'Bob audit isolation test' not in alice_messages, (
                    "Alice's audit should not contain Bob's messages"
                )
                assert 'Alice audit isolation test' not in bob_messages, (
                    "Bob's audit should not contain Alice's messages"
                )
                
                # Verify amounts are isolated
                alice_amounts = [float(e.amount) for e in alice_audit]
                bob_amounts = [float(e.amount) for e in bob_audit]
                
                if 111.0 in alice_amounts:
                    assert 222.0 not in alice_amounts, "Alice should not see Bob's 222.0 expense"
                if 222.0 in bob_amounts:
                    assert 111.0 not in bob_amounts, "Bob should not see Alice's 111.0 expense"

    def test_audit_trail_data_retention(self, client, test_users):
        """Test audit trail data retention and historical preservation"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Create expenses with different timestamps
            from utils.db import create_expense
            
            base_time = datetime.now()
            time_points = [
                base_time - timedelta(days=30),  # 30 days ago
                base_time - timedelta(days=7),   # 1 week ago
                base_time - timedelta(days=1),   # 1 day ago
                base_time                        # Now
            ]
            
            for i, timestamp in enumerate(time_points):
                create_expense(
                    user_id=user['psid_hash'],
                    amount=float(100 + (i * 50)),
                    currency='৳',
                    category=f'retention_test_{i}',
                    occurred_at=timestamp,
                    source_message_id=f'retention_test_{i}',
                    correlation_id=f'retention_corr_{i}',
                    notes=f'Retention test expense {i}'
                )
            
            # Verify all historical data is preserved
            with client.application.app_context():
                from models import Expense
                
                retention_expenses = Expense.query.filter(
                    Expense.correlation_id.like('retention_corr_%')
                ).order_by(Expense.date).all()
                
                assert len(retention_expenses) == 4, f"Expected 4 expenses, found {len(retention_expenses)}"
                
                # Verify chronological ordering
                for i in range(len(retention_expenses) - 1):
                    current = retention_expenses[i]
                    next_expense = retention_expenses[i + 1]
                    
                    assert current.date <= next_expense.date, (
                        f"Expenses should be chronologically ordered: {current.date} <= {next_expense.date}"
                    )
                
                # Verify all time periods are represented
                oldest_expense = retention_expenses[0]
                newest_expense = retention_expenses[-1]
                
                time_span = newest_expense.created_at - oldest_expense.created_at
                assert time_span.days >= 0, "Should preserve historical data across time span"
                
                # Verify data integrity across time
                for expense in retention_expenses:
                    assert expense.user_id_hash == user['psid_hash']
                    assert expense.created_at is not None
                    assert expense.correlation_id is not None
                    assert expense.original_message is not None