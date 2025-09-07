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


class TestSupabaseTest:
    """Test Supabase connectivity smoke test endpoint"""
    
    def test_missing_environment_variables(self, client):
        """Test endpoint returns 503 when environment variables are missing"""
        with patch.dict(os.environ, {}, clear=True):
            response = client.get('/supabase-test')
            
            assert response.status_code == 503
            assert response.is_json
            data = response.get_json()
            assert "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables required" in data["error"]
    
    def test_successful_supabase_connection(self, client, mock_supabase_env, requests_mock):
        """Test successful Supabase connection returns object list"""
        # Mock successful Supabase API response
        mock_objects = [
            {
                "name": "user123/document.pdf",
                "id": "uuid-123",
                "updated_at": "2025-09-07T10:00:00.000Z",
                "created_at": "2025-09-07T09:00:00.000Z",
                "metadata": {
                    "eTag": "\"abc123\"",
                    "size": 1024,
                    "mimetype": "application/pdf"
                }
            }
        ]
        
        requests_mock.get(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            json=mock_objects,
            status_code=200
        )
        
        response = client.get('/supabase-test')
        
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "user123/document.pdf"
        assert data[0]["metadata"]["size"] == 1024
    
    def test_empty_bucket_response(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns empty array for empty bucket"""
        # Mock empty bucket response
        requests_mock.get(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            json=[],
            status_code=200
        )
        
        response = client.get('/supabase-test')
        
        assert response.status_code == 200
        assert response.is_json
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_supabase_timeout(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns 503 on timeout"""
        import requests
        
        # Mock timeout exception
        requests_mock.get(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            exc=requests.exceptions.Timeout
        )
        
        response = client.get('/supabase-test')
        
        assert response.status_code == 503
        assert response.is_json
        data = response.get_json()
        assert "Supabase request timeout (3s exceeded)" in data["error"]
    
    def test_supabase_connection_error(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns 503 on connection error"""
        import requests
        
        # Mock connection error
        requests_mock.get(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            exc=requests.exceptions.ConnectionError("Connection failed")
        )
        
        response = client.get('/supabase-test')
        
        assert response.status_code == 503
        assert response.is_json
        data = response.get_json()
        assert "Supabase connection failed" in data["error"]
    
    def test_supabase_http_error(self, client, mock_supabase_env, requests_mock):
        """Test endpoint returns 503 on HTTP error from Supabase"""
        # Mock HTTP 401 Unauthorized
        requests_mock.get(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            status_code=401,
            text="Unauthorized"
        )
        
        response = client.get('/supabase-test')
        
        assert response.status_code == 503
        assert response.is_json
        data = response.get_json()
        assert "Supabase connection failed" in data["error"]
    
    def test_correct_headers_sent(self, client, mock_supabase_env, requests_mock):
        """Test that correct headers are sent to Supabase API"""
        requests_mock.get(
            'https://test-project.supabase.co/storage/v1/object/list/test-bucket',
            json=[],
            status_code=200
        )
        
        response = client.get('/supabase-test')
        
        assert response.status_code == 200
        
        # Verify the request was made with correct headers
        assert len(requests_mock.request_history) == 1
        request = requests_mock.request_history[0]
        assert request.headers['Authorization'] == 'Bearer test-service-key-12345'
        assert request.headers['apikey'] == 'test-service-key-12345'
    
    def test_default_bucket_name(self, client, requests_mock):
        """Test that default bucket name is used when SUPABASE_BUCKET is not set"""
        with patch.dict(os.environ, {
            'SUPABASE_URL': 'https://test-project.supabase.co',
            'SUPABASE_SERVICE_KEY': 'test-service-key-12345'
            # SUPABASE_BUCKET not set, should default to 'user-assets'
        }):
            requests_mock.get(
                'https://test-project.supabase.co/storage/v1/object/list/user-assets',
                json=[],
                status_code=200
            )
            
            response = client.get('/supabase-test')
            
            assert response.status_code == 200
            # Verify the request was made to the default bucket
            assert len(requests_mock.request_history) == 1
            request = requests_mock.request_history[0]
            assert '/object/list/user-assets' in request.url