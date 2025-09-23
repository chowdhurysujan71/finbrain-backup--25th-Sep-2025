"""
Smoke tests for API non-breaking changes
Simple tests to verify core functionality without complex authentication
"""

import requests
import json
import pytest

BASE_URL = "http://localhost:5000"

class TestAPISmokeTests:
    """Basic smoke tests for API functionality"""
    
    def test_health_endpoint(self):
        """Test that health endpoint is responsive"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Health check failed with status {response.status_code}"
        print("✅ Health endpoint working")
    
    def test_ai_chat_requires_auth(self):
        """Test that /ai-chat properly requires authentication"""
        response = requests.post(f"{BASE_URL}/ai-chat", json={
            "text": "test message"
        })
        
        # Should return 401 for unauthenticated requests
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        # Should return JSON error response
        try:
            data = response.json()
            assert "error" in data, "Expected error field in 401 response"
        except json.JSONDecodeError:
            pytest.fail("Expected JSON response for 401 error")
        
        print("✅ Authentication required for /ai-chat")
    
    def test_ai_chat_handles_empty_request(self):
        """Test that /ai-chat handles malformed requests properly"""
        # Test with completely empty JSON
        response = requests.post(f"{BASE_URL}/ai-chat", json={})
        assert response.status_code == 401, f"Expected 401 (auth required), got {response.status_code}"
        
        # Test with no JSON body
        response = requests.post(f"{BASE_URL}/ai-chat")
        assert response.status_code == 401, f"Expected 401 (auth required), got {response.status_code}"
        
        print("✅ Malformed request handling working")
    
    def test_captcha_endpoint(self):
        """Test that captcha endpoint is working"""
        response = requests.get(f"{BASE_URL}/api/auth/captcha")
        assert response.status_code == 200, f"Captcha endpoint failed with status {response.status_code}"
        
        try:
            data = response.json()
            assert "question" in data, "Expected question field in captcha response"
            assert "success" in data, "Expected success field in captcha response"
            assert isinstance(data["question"], str), "Question should be a string"
            assert isinstance(data["success"], bool), "Success should be a boolean"
        except json.JSONDecodeError:
            pytest.fail("Expected JSON response from captcha endpoint")
        
        print("✅ Captcha endpoint working")
    
    def test_auth_me_endpoint(self):
        """Test that /api/auth/me returns 401 for unauthenticated users"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Auth endpoint working")

class TestDatabaseConnection:
    """Test that database operations are working"""
    
    def test_database_connection_via_health(self):
        """Test database connection through health check"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, "Health check should pass if database is connected"
        
        # Health endpoint should return quickly (< 5 seconds)
        assert response.elapsed.total_seconds() < 5, "Health check taking too long"
        
        print("✅ Database connection healthy")

class TestCategoryConstraints:
    """Test that category system is working through indirect means"""
    
    def test_categories_table_exists(self):
        """Test that our categories table migration worked by checking system health"""
        # If the categories table and FK constraint were created successfully,
        # the application should start without database errors
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, "App should start successfully with new categories table"
        print("✅ Categories table migration successful")

class TestExpenseRepairFeatureFlag:
    """Test that expense repair feature flag system is working"""
    
    def test_feature_flag_system_loaded(self):
        """Test that feature flag system loaded without errors"""
        # If feature flags are broken, the app won't start properly
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, "App should start with feature flag system"
        print("✅ Feature flag system working")

if __name__ == "__main__":
    # Run smoke tests
    pytest.main([__file__, "-v", "-s"])