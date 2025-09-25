"""
Tests for Supabase Storage asset management endpoints
"""
import os
from unittest.mock import patch

import pytest

from app import app


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_env():
    """Mock environment variables for testing"""
    with patch.dict(os.environ, {
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_KEY': 'test-service-key',
        'SUPABASE_BUCKET': 'test-bucket'
    }):
        yield


class TestUploadURL:
    """Test upload URL generation endpoint"""
    
    def test_missing_user_id_header(self, client, mock_env):
        """Test upload URL request without X-User-ID header returns 401"""
        response = client.post('/assets/upload-url', 
                             json={"path": "user123/test.jpg", "content_type": "image/jpeg", "size": 1024})
        
        assert response.status_code == 401
        assert response.is_json
        data = response.get_json()
        assert "X-User-ID header required" in data["error"]
    
    def test_missing_json_body(self, client, mock_env):
        """Test upload URL request without JSON body returns 400"""
        response = client.post('/assets/upload-url',
                             headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 400
        assert "JSON body required" in response.get_json()["error"]
    
    def test_missing_required_fields(self, client, mock_env):
        """Test upload URL request with missing required fields returns 400"""
        response = client.post('/assets/upload-url',
                             headers={'X-User-ID': 'user123'},
                             json={"path": "user123/test.jpg"})  # Missing content_type and size
        
        assert response.status_code == 400
        assert "Missing required fields" in response.get_json()["error"]
    
    def test_invalid_path_prefix(self, client, mock_env):
        """Test upload URL request with wrong path prefix returns 403"""
        response = client.post('/assets/upload-url',
                             headers={'X-User-ID': 'user123'},
                             json={"path": "wrong_user/test.jpg", "content_type": "image/jpeg", "size": 1024})
        
        assert response.status_code == 403
        assert "Path must start with 'user123/'" in response.get_json()["error"]
    
    def test_invalid_content_type(self, client, mock_env):
        """Test upload URL request with disallowed content type returns 400"""
        response = client.post('/assets/upload-url',
                             headers={'X-User-ID': 'user123'},
                             json={"path": "user123/test.exe", "content_type": "application/x-executable", "size": 1024})
        
        assert response.status_code == 400
        data = response.get_json()
        assert "Content type 'application/x-executable' not allowed" in data["error"]
        assert "allowed_types" in data
    
    def test_file_too_large(self, client, mock_env):
        """Test upload URL request with file too large returns 400"""
        large_size = 11 * 1024 * 1024  # 11 MB
        response = client.post('/assets/upload-url',
                             headers={'X-User-ID': 'user123'},
                             json={"path": "user123/test.jpg", "content_type": "image/jpeg", "size": large_size})
        
        assert response.status_code == 400
        assert "exceeds maximum" in response.get_json()["error"]
    
    def test_successful_upload_url(self, client, mock_env, requests_mock):
        """Test successful upload URL generation"""
        # Mock Supabase API response
        requests_mock.post(
            'https://test.supabase.co/storage/v1/object/sign/test-bucket/user123/test.jpg',
            json={"signedURL": "/storage/v1/object/sign/test-bucket/user123/test.jpg?token=abc123"}
        )
        
        response = client.post('/assets/upload-url',
                             headers={'X-User-ID': 'user123'},
                             json={"path": "user123/test.jpg", "content_type": "image/jpeg", "size": 1024})
        
        assert response.status_code == 200
        data = response.get_json()
        assert "upload_url" in data
        assert "expires_in" in data
        assert "path" in data
        assert data["path"] == "user123/test.jpg"
        assert data["expires_in"] == 60
    
    def test_supabase_api_error(self, client, mock_env, requests_mock):
        """Test handling of Supabase API errors"""
        # Mock Supabase API error
        requests_mock.post(
            'https://test.supabase.co/storage/v1/object/sign/test-bucket/user123/test.jpg',
            status_code=500,
            text="Internal Server Error"
        )
        
        response = client.post('/assets/upload-url',
                             headers={'X-User-ID': 'user123'},
                             json={"path": "user123/test.jpg", "content_type": "image/jpeg", "size": 1024})
        
        assert response.status_code == 500
        assert "Internal server error" in response.get_json()["error"]


class TestDownloadURL:
    """Test download URL generation endpoint"""
    
    def test_missing_user_id_header(self, client, mock_env):
        """Test download URL request without X-User-ID header returns 401"""
        response = client.get('/assets/download-url?path=user123/test.jpg')
        
        assert response.status_code == 401
        assert "X-User-ID header required" in response.get_json()["error"]
    
    def test_missing_path_parameter(self, client, mock_env):
        """Test download URL request without path parameter returns 400"""
        response = client.get('/assets/download-url',
                            headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 400
        assert "path query parameter required" in response.get_json()["error"]
    
    def test_invalid_path_prefix(self, client, mock_env):
        """Test download URL request with wrong path prefix returns 403"""
        response = client.get('/assets/download-url?path=wrong_user/test.jpg',
                            headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 403
        assert "Path must start with 'user123/'" in response.get_json()["error"]
    
    def test_successful_download_url(self, client, mock_env, requests_mock):
        """Test successful download URL generation"""
        # Mock Supabase API response
        requests_mock.post(
            'https://test.supabase.co/storage/v1/object/sign/test-bucket/user123/test.jpg',
            json={"signedURL": "/storage/v1/object/test-bucket/user123/test.jpg?token=xyz789"}
        )
        
        response = client.get('/assets/download-url?path=user123/test.jpg',
                            headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert "download_url" in data
        assert "expires_in" in data
        assert data["expires_in"] == 60
        # Should convert relative URL to absolute
        assert data["download_url"].startswith("https://test.supabase.co")


class TestDeleteAsset:
    """Test asset deletion endpoint"""
    
    def test_delete_disabled_by_default(self, client, mock_env):
        """Test delete endpoint returns 403 when feature flag is disabled"""
        response = client.delete('/assets/?path=user123/test.jpg',
                               headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 403
        assert "Asset deletion not enabled" in response.get_json()["error"]
    
    @patch.dict(os.environ, {'ASSETS_ALLOW_DELETE': 'true'})
    def test_missing_user_id_header(self, client, mock_env):
        """Test delete request without X-User-ID header returns 401"""
        response = client.delete('/assets/?path=user123/test.jpg')
        
        assert response.status_code == 401
        assert "X-User-ID header required" in response.get_json()["error"]
    
    @patch.dict(os.environ, {'ASSETS_ALLOW_DELETE': 'true'})
    def test_missing_path_parameter(self, client, mock_env):
        """Test delete request without path parameter returns 400"""
        response = client.delete('/assets/',
                               headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 400
        assert "path query parameter required" in response.get_json()["error"]
    
    @patch.dict(os.environ, {'ASSETS_ALLOW_DELETE': 'true'})
    def test_invalid_path_prefix(self, client, mock_env):
        """Test delete request with wrong path prefix returns 403"""
        response = client.delete('/assets/?path=wrong_user/test.jpg',
                               headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 403
        assert "Path must start with 'user123/'" in response.get_json()["error"]
    
    @patch.dict(os.environ, {'ASSETS_ALLOW_DELETE': 'true'})
    def test_successful_delete(self, client, mock_env, requests_mock):
        """Test successful asset deletion"""
        # Mock Supabase delete API response
        requests_mock.delete(
            'https://test.supabase.co/storage/v1/object/test-bucket/user123/test.jpg',
            status_code=200
        )
        
        response = client.delete('/assets/?path=user123/test.jpg',
                               headers={'X-User-ID': 'user123'})
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["path"] == "user123/test.jpg"


class TestRequestIDPropagation:
    """Test X-Request-ID header propagation in asset endpoints"""
    
    def test_request_id_in_response_headers(self, client, mock_env, requests_mock):
        """Test that X-Request-ID header is included in responses"""
        requests_mock.post(
            'https://test.supabase.co/storage/v1/object/sign/test-bucket/user123/test.jpg',
            json={"signedURL": "/storage/v1/object/sign/test-bucket/user123/test.jpg?token=abc123"}
        )
        
        test_request_id = "test-request-456"
        response = client.post('/assets/upload-url',
                             headers={
                                 'X-User-ID': 'user123',
                                 'X-Request-ID': test_request_id
                             },
                             json={"path": "user123/test.jpg", "content_type": "image/jpeg", "size": 1024})
        
        assert response.headers.get('X-Request-ID') == test_request_id


class TestContentTypeValidation:
    """Test content type allowlist validation"""
    
    def test_allowed_content_types(self, client, mock_env, requests_mock):
        """Test that all allowed content types are accepted"""
        allowed_types = [
            'image/png', 'image/jpeg', 'application/pdf',
            'text/plain', 'application/json'
        ]
        
        # Set up a single mock that will be used for all requests
        requests_mock.post(
            'https://test.supabase.co/storage/v1/object/sign/test-bucket/user123/test.txt',
            json={"signedURL": "/signed/url"}
        )
        
        for content_type in allowed_types:
            response = client.post('/assets/upload-url',
                                 headers={'X-User-ID': 'user123'},
                                 json={"path": "user123/test.txt", "content_type": content_type, "size": 1024})
            
            assert response.status_code == 200, f"Content type {content_type} should be allowed"