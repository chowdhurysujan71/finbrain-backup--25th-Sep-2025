#!/usr/bin/env python3
"""
Simplified Real-Data Tests for Banner System

Fixed version that works with the actual codebase structure.
Tests core functionality without complex mocking.
"""

import os
import sys
import json
from datetime import datetime, timedelta, UTC
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_test_environment():
    """Setup test environment variables."""
    os.environ['ENVIRONMENT'] = 'test'
    os.environ['NUDGES_ENABLED'] = 'true'
    os.environ['TESTING'] = 'true'
    
def test_feature_flags():
    """Test feature flag functionality."""
    print("🏁 Testing Feature Flags...")
    
    try:
        # Import the actual functions that exist
        from utils.feature_flags import can_use_nudges, _is_master_user, get_nudging_features_status
        
        # Test master user detection  
        master_result = _is_master_user("chowdhurysujan71@gmail.com")
        regular_result = _is_master_user("test@example.com")
        
        assert master_result is True, "Master user not detected"
        assert regular_result is False, "Regular user incorrectly detected as master"
        
        # Test nudges enablement
        master_nudges = can_use_nudges("chowdhurysujan71@gmail.com")
        regular_nudges = can_use_nudges("test@example.com")
        
        # Both should be enabled with NUDGES_ENABLED=true
        assert master_nudges is True, "Master user nudges disabled"
        assert regular_nudges is True, "Regular user nudges disabled"
        
        # Test status function
        status = get_nudging_features_status("test@example.com")
        assert isinstance(status, dict), "Status is not a dict"
        assert 'nudges_enabled' in status, "Status missing nudges_enabled"
        
        print("✅ Feature flags working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Feature flag test failed: {e}")
        return False

def test_models_import():
    """Test that models can be imported and used."""
    print("📋 Testing Models...")
    
    try:
        from models import Banner
        
        # Check that Banner model has required attributes
        assert hasattr(Banner, 'user_id_hash'), "Banner missing user_id_hash"
        assert hasattr(Banner, 'banner_type'), "Banner missing banner_type"
        assert hasattr(Banner, 'title'), "Banner missing title"
        assert hasattr(Banner, 'message'), "Banner missing message"
        assert hasattr(Banner, 'expires_at'), "Banner missing expires_at"
        
        print("✅ Models imported and structured correctly")
        return True
        
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False

def test_test_clock_basic():
    """Test basic test clock functionality without Flask context."""
    print("🕐 Testing Test Clock...")
    
    try:
        from utils.test_clock import format_test_time, create_test_headers, is_testing_environment
        
        # Test basic functions that don't need request context
        current_time = datetime.now(UTC)
        
        # Test formatting
        formatted = format_test_time(current_time)
        assert isinstance(formatted, str), "Formatted time is not a string"
        assert formatted.endswith('Z'), "Formatted time doesn't end with Z"
        
        # Test header creation
        headers = create_test_headers(current_time)
        assert isinstance(headers, dict), "Headers is not a dict"
        assert 'X-Test-Now' in headers, "Headers missing X-Test-Now"
        
        # Test environment detection
        is_test_env = is_testing_environment()
        assert is_test_env is True, "Test environment not detected"
        
        print("✅ Test clock basic functionality working")
        return True
        
    except Exception as e:
        print(f"❌ Test clock test failed: {e}")
        return False

def test_health_endpoints():
    """Test health endpoints without authentication."""
    print("🏥 Testing Health Endpoints...")
    
    try:
        from app import app
        
        with app.test_client() as client:
            # Test health endpoints (they require auth so we expect redirects/errors)
            response = client.get('/api/health/banners')
            assert response.status_code in [302, 401, 403], f"Unexpected status: {response.status_code}"
            
            response = client.get('/api/health/nudges')
            assert response.status_code in [302, 401, 403], f"Unexpected status: {response.status_code}"
            
        print("✅ Health endpoints responding correctly")
        return True
        
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False

def test_routes_import():
    """Test that nudge routes can be imported."""
    print("🛣️  Testing Routes Import...")
    
    try:
        # Try to import the routes module
        import routes_nudges
        
        # Check that it has the expected blueprint
        assert hasattr(routes_nudges, 'nudges_bp'), "Missing nudges_bp blueprint"
        
        print("✅ Nudge routes imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Routes import test failed: {e}")
        return False

def test_database_models_basic():
    """Test basic database model functionality."""
    print("💾 Testing Database Models...")
    
    try:
        from app import app, db
        from models import Banner
        
        with app.app_context():
            # Test that we can create the Banner model structure
            # (don't actually save to avoid affecting production data)
            
            banner_data = {
                'user_id_hash': 'test_hash_123',
                'banner_type': 'SPENDING_ALERT',
                'title': 'Test Banner',
                'message': 'This is a test banner',
                'priority': 1,
                'created_at': datetime.now(UTC),
                'expires_at': datetime.now(UTC) + timedelta(hours=24)
            }
            
            # Test creating banner object (without saving)
            banner = Banner(**banner_data)
            
            # Check attributes are set
            assert banner.user_id_hash == 'test_hash_123'
            assert banner.banner_type == 'SPENDING_ALERT'
            assert banner.title == 'Test Banner'
            
        print("✅ Database models working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Database model test failed: {e}")
        return False

def test_app_initialization():
    """Test that the app can be initialized."""
    print("🚀 Testing App Initialization...")
    
    try:
        from app import app
        
        # Test that app is configured
        assert app is not None, "App is None"
        assert app.config is not None, "App config is None"
        
        # Test that we can create a test client
        with app.test_client() as client:
            # Make a simple request to a non-protected endpoint
            response = client.get('/health')
            # Health endpoint should work without auth
            assert response.status_code == 200, f"Health endpoint failed: {response.status_code}"
        
        print("✅ App initialization working")
        return True
        
    except Exception as e:
        print(f"❌ App initialization test failed: {e}")
        return False

def main():
    """Run all simplified tests."""
    print("🧪 FinBrain Simplified Test Suite")
    print("=" * 50)
    
    # Setup test environment
    setup_test_environment()
    print("✅ Test environment configured")
    
    # Run tests
    test_results = [
        ("Feature Flags", test_feature_flags()),
        ("Models Import", test_models_import()),
        ("Test Clock Basic", test_test_clock_basic()),
        ("Health Endpoints", test_health_endpoints()),
        ("Routes Import", test_routes_import()),
        ("Database Models", test_database_models_basic()),
        ("App Initialization", test_app_initialization())
    ]
    
    # Results summary
    print(f"\n📊 Test Results Summary")
    print("=" * 30)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All simplified tests passed! Core functionality is working.")
        return 0
    else:
        print("⚠️  Some tests failed. Core issues need to be addressed.")
        return 1

if __name__ == '__main__':
    exit(main())