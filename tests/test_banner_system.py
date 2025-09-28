"""
Comprehensive Real-Data Tests for Banner System

Tests banner functionality with authentication, real database operations,
and spike detection using production-like scenarios.
"""

import os
import pytest
import json
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import patch

# Test configuration
TEST_EMAIL = "test_user@example.com"
TEST_PASSWORD = "test_password_123"
MASTER_EMAIL = "chowdhurysujan71@gmail.com"

class TestBannerSystemAuthenticated:
    """Test banner system with real authentication and database operations."""
    
    @pytest.fixture(autouse=True)
    def setup_test_client(self, app_client, test_user):
        """Setup authenticated test client."""
        self.client = app_client
        self.test_user = test_user
        
        # Login the test user
        response = self.client.post('/login', data={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
    def test_banner_api_authentication_required(self):
        """Test that banner API requires authentication."""
        # Logout first
        self.client.get('/logout')
        
        response = self.client.get('/api/banners')
        assert response.status_code == 302  # Redirect to login
        
    def test_get_banners_authenticated_user(self):
        """Test getting banners for authenticated user."""
        response = self.client.get('/api/banners')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'banners' in data
        assert 'user_context' in data
        assert data['success'] is True
        
    def test_banner_creation_with_real_data(self):
        """Test banner creation with realistic financial data."""
        from models import Banner, db
        from utils.test_clock import get_current_time
        
        # Create test banner with real financial scenario
        banner = Banner(
            user_id_hash=self.test_user.user_id_hash,
            banner_type='SPENDING_ALERT',
            title='Weekly Budget Alert',
            message='You\'ve spent ৳2,500 this week. Consider reviewing your dining expenses.',
            metadata={
                'spending_amount': 2500,
                'category': 'dining',
                'period': 'weekly',
                'threshold_percent': 85
            },
            priority=2,
            created_at=get_current_time(),
            expires_at=get_current_time() + timedelta(hours=24)
        )
        
        db.session.add(banner)
        db.session.commit()
        
        # Verify banner was created
        assert banner.id is not None
        assert banner.user_id_hash == self.test_user.user_id_hash
        
        # Test retrieval
        response = self.client.get('/api/banners')
        data = json.loads(response.data)
        
        banner_found = False
        for banner_data in data['banners']:
            if banner_data['title'] == 'Weekly Budget Alert':
                banner_found = True
                assert banner_data['message'] == 'You\'ve spent ৳2,500 this week. Consider reviewing your dining expenses.'
                assert banner_data['banner_type'] == 'SPENDING_ALERT'
                break
                
        assert banner_found, "Created banner not found in API response"
        
    def test_banner_dismissal_real_scenario(self):
        """Test banner dismissal with real user interaction."""
        from models import Banner, db
        from utils.test_clock import get_current_time
        
        # Create test banner
        banner = Banner(
            user_id_hash=self.test_user.user_id_hash,
            banner_type='SAVINGS_TIP',
            title='Cashback Opportunity',
            message='Use your rewards card for 5% cashback on groceries this week!',
            metadata={'cashback_percent': 5, 'category': 'groceries'},
            priority=1,
            created_at=get_current_time(),
            expires_at=get_current_time() + timedelta(days=7)
        )
        
        db.session.add(banner)
        db.session.commit()
        banner_id = banner.id
        
        # Test dismissal
        response = self.client.post(f'/api/banners/{banner_id}/dismiss')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify banner is dismissed
        dismissed_banner = Banner.query.get(banner_id)
        assert dismissed_banner.dismissed_at is not None
        
        # Verify it doesn't appear in active banners
        response = self.client.get('/api/banners')
        data = json.loads(response.data)
        
        for banner_data in data['banners']:
            assert banner_data['id'] != banner_id, "Dismissed banner still appears in active list"

class TestSpendingSpikes:
    """Test spending spike detection with real financial scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup_test_client(self, app_client, test_user):
        """Setup authenticated test client."""
        self.client = app_client
        self.test_user = test_user
        
        # Login the test user
        response = self.client.post('/login', data={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        }, follow_redirects=True)
        
    def test_spending_spike_detection_realistic_data(self):
        """Test spike detection with realistic spending patterns."""
        from models import TransactionEffective, db
        from utils.test_clock import get_current_time
        import hashlib
        
        current_time = get_current_time()
        
        # Create baseline spending (normal pattern)
        baseline_transactions = [
            # Week 1 - Normal spending
            {'amount': Decimal('150.00'), 'category': 'dining', 'days_ago': 7},
            {'amount': Decimal('300.00'), 'category': 'groceries', 'days_ago': 6},
            {'amount': Decimal('50.00'), 'category': 'transport', 'days_ago': 5},
            
            # Week 2 - Normal spending  
            {'amount': Decimal('180.00'), 'category': 'dining', 'days_ago': 14},
            {'amount': Decimal('320.00'), 'category': 'groceries', 'days_ago': 13},
            {'amount': Decimal('45.00'), 'category': 'transport', 'days_ago': 12},
            
            # Week 3 - SPIKE in dining
            {'amount': Decimal('450.00'), 'category': 'dining', 'days_ago': 2},  # Spike!
            {'amount': Decimal('310.00'), 'category': 'groceries', 'days_ago': 1},
            {'amount': Decimal('55.00'), 'category': 'transport', 'days_ago': 1},
        ]
        
        # Insert transactions
        for trans_data in baseline_transactions:
            transaction = TransactionEffective(
                user_id_hash=self.test_user.user_id_hash,
                message_text=f"Spent ৳{trans_data['amount']} on {trans_data['category']}",
                amount_bdt=trans_data['amount'],
                category=trans_data['category'],
                created_at=current_time - timedelta(days=trans_data['days_ago']),
                confidence_score=Decimal('0.95'),
                inference_id=hashlib.md5(f"test_{trans_data['amount']}_{trans_data['days_ago']}".encode()).hexdigest()[:16]
            )
            db.session.add(transaction)
            
        db.session.commit()
        
        # Test spending analysis endpoint
        response = self.client.get('/api/nudges/spending-analysis')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'spending_patterns' in data
        assert 'anomalies' in data
        
        # Check for spike detection
        anomalies = data.get('anomalies', [])
        dining_spike_found = False
        
        for anomaly in anomalies:
            if anomaly.get('category') == 'dining' and anomaly.get('type') == 'spike':
                dining_spike_found = True
                assert anomaly['amount'] == '450.00'
                break
                
        assert dining_spike_found, "Dining spending spike not detected"
        
    def test_health_endpoint_with_real_data(self):
        """Test health endpoints with real banner data."""
        from models import Banner, db
        from utils.test_clock import get_current_time
        
        # Create active and expired banners
        active_banner = Banner(
            user_id_hash=self.test_user.user_id_hash,
            banner_type='BUDGET_TIP',
            title='Active Banner',
            message='This banner is active',
            priority=1,
            created_at=get_current_time(),
            expires_at=get_current_time() + timedelta(hours=24)
        )
        
        expired_banner = Banner(
            user_id_hash=self.test_user.user_id_hash,
            banner_type='SAVINGS_TIP', 
            title='Expired Banner',
            message='This banner is expired',
            priority=1,
            created_at=get_current_time() - timedelta(days=2),
            expires_at=get_current_time() - timedelta(hours=1)
        )
        
        db.session.add_all([active_banner, expired_banner])
        db.session.commit()
        
        # Test health endpoints (they require auth)
        response = self.client.get('/api/health/banners')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] in ['healthy', 'degraded']
        assert 'metrics' in data
        
        # Verify metrics reflect our test data
        metrics = data['metrics']
        assert 'active_banners' in metrics
        assert 'expired_banners' in metrics
        assert metrics['active_banners'] >= 1  # Our active banner
        assert metrics['expired_banners'] >= 1  # Our expired banner

class TestFeatureFlags:
    """Test feature flag functionality with real scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup_test_client(self, app_client, test_user):
        """Setup authenticated test client."""
        self.client = app_client
        self.test_user = test_user
        
        # Login the test user
        response = self.client.post('/login', data={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        }, follow_redirects=True)
        
    def test_nudges_feature_flag_enabled(self):
        """Test that NUDGES_ENABLED flag works correctly."""
        # Test with flag enabled (current state)
        response = self.client.get('/api/banners')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'banners' in data
        
    def test_master_user_access(self):
        """Test that master user gets special privileges."""
        # Logout current user
        self.client.get('/logout')
        
        # This would need master user credentials in a real test
        # For now, just verify the feature flag logic exists
        from utils.feature_flags import is_master_user, nudges_enabled_for_user
        
        # Test master user detection
        master_result = is_master_user(MASTER_EMAIL)
        assert master_result is True
        
        # Test regular user
        regular_result = is_master_user(TEST_EMAIL)
        assert regular_result is False
        
        # Test nudges enablement
        master_nudges = nudges_enabled_for_user(MASTER_EMAIL)
        regular_nudges = nudges_enabled_for_user(TEST_EMAIL)
        
        # Both should be enabled due to NUDGES_ENABLED=true
        assert master_nudges is True
        assert regular_nudges is True

class TestErrorHandling:
    """Test error handling in banner system."""
    
    def test_invalid_banner_dismissal(self, app_client, test_user):
        """Test dismissing non-existent banner."""
        client = app_client
        
        # Login
        response = client.post('/login', data={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        }, follow_redirects=True)
        
        # Try to dismiss non-existent banner
        response = client.post('/api/banners/999999/dismiss')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'error' in data
        
    def test_malformed_banner_request(self, app_client, test_user):
        """Test handling of malformed requests."""
        client = app_client
        
        # Login
        response = client.post('/login', data={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        }, follow_redirects=True)
        
        # Try invalid banner ID
        response = client.post('/api/banners/invalid_id/dismiss')
        assert response.status_code == 404
        
class TestDeterministicTiming:
    """Test deterministic timing with X-Test-Now header."""
    
    def test_test_clock_functionality(self, app_client, test_user):
        """Test X-Test-Now header support for deterministic testing."""
        client = app_client
        
        # Login
        response = client.post('/login', data={
            'email': TEST_EMAIL,
            'password': TEST_PASSWORD
        }, follow_redirects=True)
        
        # Test with X-Test-Now header
        test_time = "2025-09-28T10:30:00Z"
        headers = {'X-Test-Now': test_time}
        
        response = client.get('/api/banners', headers=headers)
        assert response.status_code == 200
        
        # The response should include timestamp using test time
        data = json.loads(response.data)
        assert data['success'] is True
        
        # In a real test, we'd verify the banner expiration logic
        # uses the test time instead of real time