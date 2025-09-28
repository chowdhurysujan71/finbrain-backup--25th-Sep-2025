"""
Test Configuration and Fixtures

Provides shared test fixtures for authentication, database setup,
and test data creation.
"""

import os
import pytest
import tempfile
from datetime import datetime, UTC
from werkzeug.security import generate_password_hash

# Import app and models
from app import app, db
from models import User, Banner, TransactionEffective

TEST_EMAIL = "test_user@example.com"
TEST_PASSWORD = "test_password_123"
TEST_USERNAME = "testuser"

@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    # Configure for testing
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['LOGIN_DISABLED'] = False
    
    # Use in-memory database for tests
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    # Set test environment
    os.environ['ENVIRONMENT'] = 'test'
    os.environ['NUDGES_ENABLED'] = 'true'
    
    return app

@pytest.fixture(scope='session')
def database(app):
    """Create database schema for testing."""
    with app.app_context():
        db.create_all()
        yield db
        db.drop_all()

@pytest.fixture
def app_client(app, database):
    """Create test client with database."""
    with app.test_client() as client:
        with app.app_context():
            yield client

@pytest.fixture
def test_user(app, database):
    """Create test user for authentication."""
    with app.app_context():
        # Create test user
        user = User(
            email=TEST_EMAIL,
            username=TEST_USERNAME,
            password_hash=generate_password_hash(TEST_PASSWORD),
            name="Test User",
            created_at=datetime.now(UTC)
        )
        
        # Generate user_id_hash like the real system
        import hashlib
        user.user_id_hash = hashlib.sha256(
            f"{user.email}:{user.username}".encode()
        ).hexdigest()[:16]
        
        db.session.add(user)
        db.session.commit()
        
        yield user
        
        # Cleanup
        db.session.delete(user)
        db.session.commit()

@pytest.fixture
def master_user(app, database):
    """Create master user for privilege testing."""
    with app.app_context():
        # Create master user (hardcoded email in feature flags)
        user = User(
            email="chowdhurysujan71@gmail.com",
            username="masteruser",
            password_hash=generate_password_hash("master_password_123"),
            name="Master User",
            created_at=datetime.now(UTC)
        )
        
        # Generate user_id_hash
        import hashlib
        user.user_id_hash = hashlib.sha256(
            f"{user.email}:{user.username}".encode()
        ).hexdigest()[:16]
        
        db.session.add(user)
        db.session.commit()
        
        yield user
        
        # Cleanup
        db.session.delete(user)
        db.session.commit()

@pytest.fixture
def sample_banners(app, database, test_user):
    """Create sample banners for testing."""
    with app.app_context():
        from utils.test_clock import get_current_time
        from datetime import timedelta
        
        current_time = get_current_time()
        
        banners = [
            Banner(
                user_id_hash=test_user.user_id_hash,
                banner_type='SPENDING_ALERT',
                title='Weekly Budget Alert',
                message='You\'ve exceeded 80% of your weekly dining budget.',
                metadata={'threshold': 0.8, 'category': 'dining'},
                priority=2,
                created_at=current_time,
                expires_at=current_time + timedelta(hours=24)
            ),
            Banner(
                user_id_hash=test_user.user_id_hash,
                banner_type='SAVINGS_TIP',
                title='Cashback Opportunity',
                message='Use your rewards card for groceries this week!',
                metadata={'cashback_percent': 5},
                priority=1,
                created_at=current_time,
                expires_at=current_time + timedelta(days=7)
            ),
            Banner(
                user_id_hash=test_user.user_id_hash,
                banner_type='BUDGET_TIP',
                title='Transportation Savings',
                message='Consider using public transport to save ৳200/week.',
                metadata={'potential_savings': 200},
                priority=3,
                created_at=current_time - timedelta(hours=1),
                expires_at=current_time + timedelta(hours=23)
            )
        ]
        
        db.session.add_all(banners)
        db.session.commit()
        
        yield banners
        
        # Cleanup
        for banner in banners:
            db.session.delete(banner)
        db.session.commit()

@pytest.fixture
def sample_transactions(app, database, test_user):
    """Create sample transactions for spending analysis."""
    with app.app_context():
        from utils.test_clock import get_current_time
        from datetime import timedelta
        from decimal import Decimal
        import hashlib
        
        current_time = get_current_time()
        
        transactions = [
            TransactionEffective(
                user_id_hash=test_user.user_id_hash,
                message_text="Lunch at restaurant",
                amount_bdt=Decimal('250.00'),
                category='dining',
                created_at=current_time - timedelta(days=1),
                confidence_score=Decimal('0.95'),
                inference_id=hashlib.md5(b"lunch_restaurant").hexdigest()[:16]
            ),
            TransactionEffective(
                user_id_hash=test_user.user_id_hash,
                message_text="Grocery shopping",
                amount_bdt=Decimal('450.00'),
                category='groceries',
                created_at=current_time - timedelta(days=2),
                confidence_score=Decimal('0.92'),
                inference_id=hashlib.md5(b"grocery_shopping").hexdigest()[:16]
            ),
            TransactionEffective(
                user_id_hash=test_user.user_id_hash,
                message_text="Bus fare",
                amount_bdt=Decimal('30.00'),
                category='transport',
                created_at=current_time - timedelta(days=1),
                confidence_score=Decimal('0.98'),
                inference_id=hashlib.md5(b"bus_fare").hexdigest()[:16]
            )
        ]
        
        db.session.add_all(transactions)
        db.session.commit()
        
        yield transactions
        
        # Cleanup
        for transaction in transactions:
            db.session.delete(transaction)
        db.session.commit()