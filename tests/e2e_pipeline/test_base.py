"""
Base E2E Test Infrastructure

Provides shared fixtures, authentication handlers, and database utilities
for comprehensive end-to-end testing of the expense data pipeline.
"""
import hashlib
import hmac
import os
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

# Import the main app and database components
from app import app, db
from models import Expense, MonthlySummary, User
from utils.identity import psid_hash


class E2ETestBase:
    """Base class for E2E testing with authentication and database management"""
    
    @pytest.fixture(scope="function")
    def test_app(self):
        """Create test Flask app with proper configuration"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SECRET_KEY'] = 'test-secret-key'
        
        with app.app_context():
            # Create all tables for testing
            db.create_all()
            yield app
            # Clean up after test
            db.session.rollback()
            db.drop_all()

    @pytest.fixture(scope="function")
    def client(self, test_app):
        """Create test client"""
        return test_app.test_client()

    @pytest.fixture(scope="function")
    def test_users(self):
        """Create test users with different authentication contexts"""
        users = {
            'alice': {
                'psid': 'test_psid_alice_12345',
                'psid_hash': psid_hash('test_psid_alice_12345'),
                'session_user_id': 'session_alice_67890',
                'x_user_id': 'xuserid_alice_54321'
            },
            'bob': {
                'psid': 'test_psid_bob_67890',
                'psid_hash': psid_hash('test_psid_bob_67890'),
                'session_user_id': 'session_bob_13579',
                'x_user_id': 'xuserid_bob_97531'
            }
        }
        
        # Create user records in database
        with app.app_context():
            for user_name, user_data in users.items():
                user = User()
                user.user_id_hash = user_data['psid_hash']
                user.platform = 'test'
                user.total_expenses = Decimal('0')
                user.expense_count = 0
                user.created_at = datetime.utcnow()
                user.last_interaction = datetime.utcnow()
                db.session.add(user)
            db.session.commit()
            
        return users

    def setup_session_auth(self, client, user_id: str):
        """Setup session-based authentication for backend API endpoints"""
        with app.app_context():
            with client.session_transaction() as session:
                session['user_id'] = user_id

    def setup_x_user_id_auth(self, user_id: str) -> dict[str, str]:
        """Setup X-User-ID header authentication for form endpoints"""
        return {'X-User-ID': user_id}

    def generate_facebook_signature(self, body: bytes, secret: str = 'test-webhook-secret') -> str:
        """Generate Facebook webhook signature for messenger authentication"""
        signature = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        return f'sha256={signature}'

    def create_facebook_webhook_payload(self, psid: str, message: str, mid: str | None = None) -> dict[str, Any]:
        """Create Facebook Messenger webhook payload"""
        if mid is None:
            mid = f"test_mid_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
        return {
            "object": "page",
            "entry": [
                {
                    "id": "test_page_id",
                    "time": int(time.time() * 1000),
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "test_page_id"},
                            "timestamp": int(time.time() * 1000),
                            "message": {
                                "mid": mid,
                                "text": message
                            }
                        }
                    ]
                }
            ]
        }

    def assert_expense_created(self, user_hash: str, expected_amount: float, expected_category: str, 
                             platform: str | None = None, correlation_id: str | None = None) -> Expense:
        """Assert that an expense was created and return the expense object"""
        with app.app_context():
            query = db.session.query(Expense).filter_by(user_id_hash=user_hash)
            
            if platform:
                query = query.filter_by(platform=platform)
            if correlation_id:
                query = query.filter_by(correlation_id=correlation_id)
                
            expenses = query.all()
            
            assert len(expenses) > 0, f"No expense found for user {user_hash}"
            
            # Find expense matching criteria
            matching_expense = None
            for expense in expenses:
                if (abs(float(expense.amount) - expected_amount) < 0.01 and 
                    expense.category.lower() == expected_category.lower()):
                    matching_expense = expense
                    break
                    
            assert matching_expense is not None, (
                f"No expense found matching amount {expected_amount} and category {expected_category}. "
                f"Found expenses: {[(float(e.amount), e.category) for e in expenses]}"
            )
            
            return matching_expense

    def assert_user_totals_updated(self, user_hash: str, expected_increase: float):
        """Assert that user totals were properly updated"""
        with app.app_context():
            user = db.session.query(User).filter_by(user_id_hash=user_hash).first()
            assert user is not None, f"User {user_hash} not found"
            assert user.expense_count > 0, "Expense count not incremented"
            assert float(user.total_expenses) >= expected_increase, (
                f"Total expenses {float(user.total_expenses)} less than expected increase {expected_increase}"
            )

    def assert_monthly_summary_updated(self, user_hash: str, month: str, expected_increase: float):
        """Assert that monthly summary was properly updated"""
        with app.app_context():
            summary = db.session.query(MonthlySummary).filter_by(
                user_id_hash=user_hash,
                month=month
            ).first()
            
            assert summary is not None, f"Monthly summary not found for {user_hash} in {month}"
            assert float(summary.total_amount) >= expected_increase, (
                f"Monthly total {float(summary.total_amount)} less than expected {expected_increase}"
            )

    def assert_no_duplicate_expenses(self, user_hash: str, correlation_id: str | None = None, mid: str | None = None):
        """Assert that no duplicate expenses were created"""
        with app.app_context():
            query = db.session.query(Expense).filter_by(user_id_hash=user_hash)
            
            if correlation_id:
                query = query.filter_by(correlation_id=correlation_id)
            if mid:
                query = query.filter_by(mid=mid)
                
            expenses = query.all()
            
            if correlation_id or mid:
                assert len(expenses) <= 1, f"Duplicate expenses found: {len(expenses)}"
            
            # Check for functional duplicates (same user, amount, category, time within 1 minute)
            expense_groups = {}
            for expense in expenses:
                key = (
                    expense.user_id_hash,
                    float(expense.amount),
                    expense.category,
                    expense.date
                )
                if key not in expense_groups:
                    expense_groups[key] = []
                expense_groups[key].append(expense)
            
            for key, group in expense_groups.items():
                if len(group) > 1:
                    # Check if they're within 1 minute of each other
                    times = [e.created_at for e in group]
                    times.sort()
                    for i in range(1, len(times)):
                        time_diff = times[i] - times[i-1]
                        if time_diff.total_seconds() < 60:
                            raise AssertionError(f"Potential duplicate expenses found: {key}")

    def assert_user_isolation(self, user1_hash: str, user2_hash: str):
        """Assert that users cannot access each other's data (IDOR prevention)"""
        with app.app_context():
            # Check expenses
            user1_expenses = db.session.query(Expense).filter_by(user_id_hash=user1_hash).all()
            user2_expenses = db.session.query(Expense).filter_by(user_id_hash=user2_hash).all()
            
            # Verify no cross-contamination
            for expense in user1_expenses:
                assert expense.user_id_hash == user1_hash, "User 1 has expense from user 2"
            
            for expense in user2_expenses:
                assert expense.user_id_hash == user2_hash, "User 2 has expense from user 1"
            
            # Check monthly summaries
            user1_summaries = db.session.query(MonthlySummary).filter_by(user_id_hash=user1_hash).all()
            user2_summaries = db.session.query(MonthlySummary).filter_by(user_id_hash=user2_hash).all()
            
            for summary in user1_summaries:
                assert summary.user_id_hash == user1_hash, "User 1 has summary from user 2"
            
            for summary in user2_summaries:
                assert summary.user_id_hash == user2_hash, "User 2 has summary from user 1"

    def create_test_expenses_history(self, user_hash: str, count: int = 5) -> list[Expense]:
        """Create test expense history for testing recent expenses and totals"""
        expenses = []
        
        with app.app_context():
            for i in range(count):
                expense = Expense()
                expense.user_id = user_hash
                expense.user_id_hash = user_hash
                expense.amount = Decimal(str(10.0 + i))
                expense.category = f"test_category_{i}"
                expense.description = f"Test expense {i}"
                expense.date = date.today() - timedelta(days=i)
                expense.time = datetime.now().time()
                expense.month = (date.today() - timedelta(days=i)).strftime('%Y-%m')
                expense.unique_id = str(uuid.uuid4())
                expense.platform = "test"
                expense.correlation_id = str(uuid.uuid4())
                expense.created_at = datetime.utcnow() - timedelta(hours=i)
                
                db.session.add(expense)
                expenses.append(expense)
                
            db.session.commit()
            
        return expenses

    def mock_environment_secrets(self):
        """Mock environment variables for testing"""
        return patch.dict(os.environ, {
            'SESSION_SECRET': 'test-session-secret',
            'FACEBOOK_WEBHOOK_SECRET': 'test-webhook-secret',
            'DATABASE_URL': os.environ.get('DATABASE_URL', 'postgresql://localhost/test'),
            'AI_RL_USER_LIMIT': '10',
            'AI_RL_WINDOW_SEC': '3600',
            'AI_RL_GLOBAL_LIMIT': '100',
            'MSG_MAX_CHARS': '2000'
        })