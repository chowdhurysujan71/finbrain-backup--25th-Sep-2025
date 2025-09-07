"""
Tests for Supabase connectivity smoke test endpoint
"""
import pytest
import json
from unittest.mock import patch
import os

from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_supabase_env():
    """Mock Supabase environment variables"""
    with patch.dict(os.environ, {
        'SUPABASE_URL': 'https://test-project.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key-12345',
        'SUPABASE_BUCKET': 'test-bucket'
    }):
        yield


class TestSupabaseSmoke:
    """Test Supabase connectivity smoke test endpoint"""
    
    def test_missing_environment_variables(self, client):
        """Test endpoint returns 503 when environment variables are missing"""
        with patch.dict(os.environ, {}, clear=True):
            response = client.get('/supabase-smoke')
            
            assert response.status_code == 503
            assert response.is_json
            data = response.get_json()
            assert data["connected"] is False
            assert "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required" in data["error"]
    
    def test_successful_supabase_connection_with_objects(self, client, mock_supabase_env, requests_mock):
        """Test successful Supabase connection returns object list"""
        # Mock successful Supabase API response with objects
        mock_objects = [
            {
                "name": "testuser/hello.txt",
                "id": "uuid-123",
                "updated_at": "2025-09-07T10:00:00.000Z",
                "created_at": "2025-09-07T09:00:00.000Z",
                "metadata": {
                    "eTag": "\"abc123\"",
                    "size": 12,
                    "mimetype": "text/plain"
                }
            }
        ]
        
        requests_mock.post(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            json=mock_objects,
            status_code=200
        )
        
        response = client.get('/supabase-smoke')
        
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert data["connected"] is True
        assert "objects" in data
        assert isinstance(data["objects"], list)
        assert len(data["objects"]) == 1
        assert data["objects"][0]["name"] == "testuser/hello.txt"
        assert data["objects"][0]["metadata"]["size"] == 12
    
    def test_successful_supabase_connection_empty_bucket(self, client, mock_supabase_env, requests_mock):
        """Test successful connection to empty bucket returns empty array"""
        # Mock empty bucket response
        requests_mock.post(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            json=[],
            status_code=200
        )
        
        response = client.get('/supabase-smoke')
        
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert data["connected"] is True
        assert data["objects"] == []
    
    def test_supabase_timeout(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns 503 on timeout"""
        import requests
        
        # Mock timeout exception
        requests_mock.post(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            exc=requests.exceptions.Timeout
        )
        
        response = client.get('/supabase-smoke')
        
        assert response.status_code == 503
        assert response.is_json
        data = response.get_json()
        assert data["connected"] is False
        assert "Supabase request timeout (3s exceeded)" in data["error"]
    
    def test_supabase_connection_error(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns 503 on connection error"""
        import requests
        
        # Mock connection error
        requests_mock.post(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            exc=requests.exceptions.ConnectionError("Connection failed")
        )
        
        response = client.get('/supabase-smoke')
        
        assert response.status_code == 503
        assert response.is_json
        data = response.get_json()
        assert data["connected"] is False
        assert "Supabase connection failed" in data["error"]
    
    def test_supabase_http_error_401(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns 503 on HTTP 401 Unauthorized"""
        # Mock HTTP 401 Unauthorized
        requests_mock.post(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            status_code=401,
            text="Unauthorized"
        )
        
        response = client.get('/supabase-smoke')
        
        assert response.status_code == 503
        assert response.is_json
        data = response.get_json()
        assert data["connected"] is False
        assert "Supabase connection failed" in data["error"]
    
    def test_supabase_http_error_404(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns 503 on HTTP 404 Not Found (bucket missing)"""
        # Mock HTTP 404 Not Found
        requests_mock.post(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            status_code=404,
            text="Not Found"
        )
        
        response = client.get('/supabase-smoke')
        
        assert response.status_code == 503
        assert response.is_json
        data = response.get_json()
        assert data["connected"] is False
        assert "Supabase connection failed" in data["error"]
    
    def test_correct_request_format(self, client, mock_supabase_env, requests_mock):
        """Test that correct POST request format is sent to Supabase"""
        requests_mock.post(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            json=[],
            status_code=200
        )
        
        response = client.get('/supabase-smoke')
        
        assert response.status_code == 200
        
        # Verify the request was made with correct format
        assert len(requests_mock.request_history) == 1
        request = requests_mock.request_history[0]
        
        # Check headers
        assert request.headers['Authorization'] == 'Bearer test-service-key-12345'
        assert request.headers['apikey'] == 'test-service-key-12345'
        assert request.headers['Content-Type'] == 'application/json'
        
        # Check request body
        request_body = request.json()
        assert request_body["prefix"] == ""
        assert request_body["limit"] == 1
        assert request_body["offset"] == 0
    
    def test_default_bucket_name(self, client, requests_mock):
        """Test that default bucket name is used when SUPABASE_BUCKET is not set"""
        with patch.dict(os.environ, {
            'SUPABASE_URL': 'https://test-project.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-service-key-12345'
            # SUPABASE_BUCKET not set, should default to 'user-assets'
        }):
            requests_mock.post(
                'https://test-project.supabase.co/storage/v1/object/list/user-assets',
                json=[],
                status_code=200
            )
            
            response = client.get('/supabase-smoke')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["connected"] is True
            
            # Verify the request was made to the default bucket
            assert len(requests_mock.request_history) == 1
            request = requests_mock.request_history[0]
            assert '/object/list/user-assets' in request.url
    
    def test_unexpected_exception_handling(self, client, mock_supabase_env):
        """Test that unexpected exceptions are handled gracefully"""
        with patch('requests.post', side_effect=Exception("Unexpected error")):
            response = client.get('/supabase-smoke')
            
            assert response.status_code == 503
            assert response.is_json
            data = response.get_json()
            assert data["connected"] is False
            assert "Unexpected error" in data["error"]