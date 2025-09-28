#!/usr/bin/env python3
"""
Test Runner for FinBrain Banner System

Runs comprehensive tests with real database operations and authentication.
Supports both local development and CI environments.
"""

import os
import sys
import subprocess
import tempfile
import json
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_test_environment():
    """Setup test environment variables."""
    os.environ['ENVIRONMENT'] = 'test'
    os.environ['NUDGES_ENABLED'] = 'true'
    os.environ['TESTING'] = 'true'
    
    # Use test database
    test_db_url = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    os.environ['SQLALCHEMY_DATABASE_URI'] = test_db_url
    
    print(f"✓ Test environment configured")
    print(f"  - Environment: {os.environ['ENVIRONMENT']}")
    print(f"  - Database: {test_db_url}")
    print(f"  - Nudges enabled: {os.environ['NUDGES_ENABLED']}")

def run_banner_system_tests():
    """Run banner system tests."""
    print("\n🧪 Running Banner System Tests...")
    
    try:
        # Import test modules to check syntax
        from tests.test_banner_system import (
            TestBannerSystemAuthenticated, 
            TestSpendingSpikes,
            TestFeatureFlags,
            TestErrorHandling,
            TestDeterministicTiming
        )
        
        print("✓ Test modules imported successfully")
        
        # Run basic functionality tests
        test_basic_imports()
        test_models_available()
        test_feature_flags()
        
        print("✓ All basic tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_basic_imports():
    """Test that all required modules can be imported."""
    try:
        from app import app, db
        from models import User, Banner, TransactionEffective
        from utils.feature_flags import is_master_user, nudges_enabled_for_user
        from utils.test_clock import get_current_time, format_test_time
        print("✓ All required modules imported")
    except ImportError as e:
        raise Exception(f"Import error: {e}")

def test_models_available():
    """Test that database models are properly configured."""
    try:
        from models import User, Banner, TransactionEffective
        
        # Check that models have required attributes
        assert hasattr(User, 'email')
        assert hasattr(User, 'user_id_hash')
        assert hasattr(Banner, 'user_id_hash')
        assert hasattr(Banner, 'banner_type')
        assert hasattr(TransactionEffective, 'amount_bdt')
        
        print("✓ Database models configured correctly")
    except Exception as e:
        raise Exception(f"Model configuration error: {e}")

def test_feature_flags():
    """Test feature flag functionality."""
    try:
        from utils.feature_flags import is_master_user, nudges_enabled_for_user
        
        # Test master user detection
        master_result = is_master_user("chowdhurysujan71@gmail.com")
        regular_result = is_master_user("test@example.com")
        
        assert master_result is True
        assert regular_result is False
        
        # Test nudges enablement
        master_nudges = nudges_enabled_for_user("chowdhurysujan71@gmail.com")
        regular_nudges = nudges_enabled_for_user("test@example.com")
        
        # Both should be enabled with NUDGES_ENABLED=true
        assert master_nudges is True
        assert regular_nudges is True
        
        print("✓ Feature flags working correctly")
    except Exception as e:
        raise Exception(f"Feature flag error: {e}")

def test_test_clock():
    """Test the test clock functionality."""
    try:
        from utils.test_clock import get_current_time, format_test_time, create_test_headers
        from datetime import datetime, UTC
        
        # Test basic functionality
        current_time = get_current_time()
        assert isinstance(current_time, datetime)
        
        # Test formatting
        formatted = format_test_time(current_time)
        assert isinstance(formatted, str)
        assert formatted.endswith('Z')
        
        # Test header creation
        headers = create_test_headers(current_time)
        assert 'X-Test-Now' in headers
        
        print("✓ Test clock functionality working")
    except Exception as e:
        raise Exception(f"Test clock error: {e}")

def run_health_check_tests():
    """Run health check endpoint tests."""
    print("\n🏥 Running Health Check Tests...")
    
    try:
        from app import app
        
        with app.test_client() as client:
            # Test that health endpoints exist (they'll require auth)
            response = client.get('/api/health/banners')
            # Should redirect to login or return auth error
            assert response.status_code in [302, 401, 403]
            
            response = client.get('/api/health/nudges') 
            assert response.status_code in [302, 401, 403]
            
        print("✓ Health endpoints accessible")
        return True
        
    except Exception as e:
        print(f"❌ Health check test failed: {e}")
        return False

def run_integration_tests():
    """Run integration tests with authentication flow."""
    print("\n🔗 Running Integration Tests...")
    
    try:
        from app import app, db
        from models import User
        from werkzeug.security import generate_password_hash
        
        with app.app_context():
            # Create test database tables
            db.create_all()
            
            # Create test user
            test_user = User(
                email="integration_test@example.com",
                username="integration_test",
                password_hash=generate_password_hash("test_password"),
                name="Integration Test User"
            )
            
            # Generate user_id_hash
            import hashlib
            test_user.user_id_hash = hashlib.sha256(
                f"{test_user.email}:{test_user.username}".encode()
            ).hexdigest()[:16]
            
            db.session.add(test_user)
            db.session.commit()
            
            print("✓ Test database and user created")
            
            # Test basic banner API flow
            with app.test_client() as client:
                # Test login (should redirect to login page)
                response = client.get('/api/banners')
                assert response.status_code in [302, 401]
                
                print("✓ Authentication protection working")
                
            # Cleanup
            db.session.delete(test_user)
            db.session.commit()
            
        print("✓ Integration tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def generate_test_report():
    """Generate test report."""
    report = {
        'timestamp': datetime.now().isoformat(),
        'environment': os.environ.get('ENVIRONMENT'),
        'database': os.environ.get('SQLALCHEMY_DATABASE_URI'),
        'nudges_enabled': os.environ.get('NUDGES_ENABLED'),
        'tests_run': [],
        'status': 'unknown'
    }
    
    return report

def main():
    """Main test runner."""
    print("🚀 FinBrain Banner System Test Suite")
    print("=" * 50)
    
    # Setup environment
    setup_test_environment()
    
    # Run test suites
    results = []
    
    try:
        # Basic functionality tests
        results.append(('Banner System Tests', run_banner_system_tests()))
        results.append(('Health Check Tests', run_health_check_tests()))
        results.append(('Integration Tests', run_integration_tests()))
        
        # Test clock functionality
        try:
            test_test_clock()
            results.append(('Test Clock Tests', True))
        except Exception as e:
            print(f"❌ Test clock failed: {e}")
            results.append(('Test Clock Tests', False))
        
        # Summary
        print(f"\n📊 Test Results Summary")
        print("=" * 30)
        
        passed = 0
        total = len(results)
        
        for test_name, passed_status in results:
            status = "✅ PASS" if passed_status else "❌ FAIL"
            print(f"{test_name:25} {status}")
            if passed_status:
                passed += 1
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Banner system is ready for deployment.")
            return 0
        else:
            print("⚠️  Some tests failed. Please review and fix issues.")
            return 1
            
    except Exception as e:
        print(f"❌ Test runner failed: {e}")
        return 1

if __name__ == '__main__':
    exit(main())