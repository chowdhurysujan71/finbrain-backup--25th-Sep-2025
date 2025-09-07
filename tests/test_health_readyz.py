"""
Tests for /health and /readyz endpoints
"""
import pytest
import os
from unittest.mock import patch, MagicMock
import psycopg

from app import app, db


@pytest.fixture
def client():
    """Create test client"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint_lightweight(client):
    """Test /health endpoint returns 200 with simple status"""
    response = client.get('/health')
    
    assert response.status_code == 200
    assert response.is_json
    
    data = response.get_json()
    assert data == {"status": "ok"}
    
    # Verify X-Request-ID header is present
    assert 'X-Request-ID' in response.headers


def test_readyz_both_ok(client):
    """Test /readyz returns 200 when DB and AI key are both OK"""
    with patch('psycopg.connect') as mock_connect, \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key', 'DATABASE_URL': 'test-db-url'}):
        
        # Mock successful DB connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        response = client.get('/readyz')
        
        assert response.status_code == 200
        assert response.is_json
        
        data = response.get_json()
        assert data['db'] is True
        assert data['ai_key_present'] is True
        # redis is informational, can be True or False
        assert 'redis' in data


def test_readyz_db_fail(client):
    """Test /readyz returns 503 when DB check fails"""
    with patch('psycopg.connect') as mock_connect, \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key', 'DATABASE_URL': 'test-db-url'}):
        
        # Mock DB connection failure
        mock_connect.side_effect = psycopg.OperationalError("Connection failed")
        
        response = client.get('/readyz')
        
        assert response.status_code == 503
        assert response.is_json
        
        data = response.get_json()
        assert data['db'] is False
        assert data['ai_key_present'] is True


def test_readyz_ai_key_missing(client):
    """Test /readyz returns 503 when AI key is missing"""
    with patch('psycopg.connect') as mock_connect, \
         patch.dict(os.environ, {}, clear=True):  # Clear AI keys
        
        # Mock successful DB connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        response = client.get('/readyz')
        
        assert response.status_code == 503
        assert response.is_json
        
        data = response.get_json()
        assert data['db'] is True
        assert data['ai_key_present'] is False


def test_readyz_both_fail(client):
    """Test /readyz returns 503 when both DB and AI key fail"""
    with patch('psycopg.connect') as mock_connect, \
         patch.dict(os.environ, {}, clear=True):  # Clear AI keys and keep minimal env
        
        # Mock DB connection failure
        mock_connect.side_effect = psycopg.OperationalError("Connection failed")
        
        response = client.get('/readyz')
        
        assert response.status_code == 503
        assert response.is_json
        
        data = response.get_json()
        assert data['db'] is False
        assert data['ai_key_present'] is False


def test_test_error_endpoint(client):
    """Test /__test_error endpoint raises RuntimeError"""
    with pytest.raises(RuntimeError, match="Sentry test error"):
        # This would normally be caught by the test client, but we want to verify
        # the endpoint actually raises the expected exception
        client.get('/__test_error')


def test_request_id_header_propagation(client):
    """Test that X-Request-ID header is propagated correctly"""
    test_request_id = "test-request-123"
    
    response = client.get('/health', headers={'X-Request-ID': test_request_id})
    
    assert response.headers.get('X-Request-ID') == test_request_id


def test_readyz_timeout_budget(client):
    """Test that /readyz completes within timeout budget"""
    import time
    
    with patch('psycopg.connect') as mock_connect, \
         patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key', 'DATABASE_URL': 'test-db-url'}):
        
        # Mock successful but not too slow connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        start_time = time.time()
        response = client.get('/readyz')
        elapsed = time.time() - start_time
        
        # Should complete well under 2s budget in test environment
        assert elapsed < 2.0
        assert response.status_code == 200