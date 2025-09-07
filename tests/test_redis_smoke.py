"""Tests for Redis smoke test endpoint"""
import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from app.routes_redis_smoke import redis_smoke_bp

@pytest.fixture
def app():
    """Create test Flask app with Redis smoke test blueprint"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(redis_smoke_bp)
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

class TestRedisSmokeEndpoint:
    """Test Redis smoke test endpoint with comprehensive mocking"""

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_redis_url(self, client):
        """Test response when REDIS_URL environment variable is missing"""
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check HTTP response
            assert response.status_code == 503
            data = response.get_json()
            assert data['connected'] is False
            assert data['error'] == "missing REDIS_URL"
            
            # Check structured logging
            mock_logger.logger.info.assert_called_once()
            log_call = mock_logger.logger.info.call_args[0][0]
            log_data = json.loads(log_call)
            assert log_data['event'] == "redis_smoke"
            assert log_data['connected'] is False
            assert 'latency_ms' in log_data
            assert log_data['error'] == "missing REDIS_URL"

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_redis_import_error(self, mock_redis_module, client):
        """Test response when redis module is not available"""
        # Mock ImportError when importing redis
        mock_redis_module.side_effect = ImportError("No module named 'redis'")
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            # Need to manually trigger the import error
            with patch('builtins.__import__') as mock_import:
                def import_side_effect(name, *args, **kwargs):
                    if name == 'redis':
                        raise ImportError("No module named 'redis'")
                    return __import__(name, *args, **kwargs)
                
                mock_import.side_effect = import_side_effect
                
                response = client.get('/redis-smoke')
                
                # Check HTTP response
                assert response.status_code == 503
                data = response.get_json()
                assert data['connected'] is False
                assert "redis package not installed" in data['error']

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_successful_redis_connection(self, mock_redis_module, client):
        """Test successful Redis connection and operations"""
        # Mock redis client
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.return_value = True
        mock_client.get.return_value = "ok"
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check Redis operations were called correctly
            mock_redis_module.from_url.assert_called_once_with(
                'redis://localhost:6379',
                socket_connect_timeout=3,
                socket_timeout=3,
                decode_responses=True
            )
            mock_client.set.assert_called_once_with("smoke:test", "ok", ex=5)
            mock_client.get.assert_called_once_with("smoke:test")
            
            # Check HTTP response
            assert response.status_code == 200
            data = response.get_json()
            assert data['connected'] is True
            assert data['value'] == "ok"
            
            # Check structured logging
            mock_logger.logger.info.assert_called_once()
            log_call = mock_logger.logger.info.call_args[0][0]
            log_data = json.loads(log_call)
            assert log_data['event'] == "redis_smoke"
            assert log_data['connected'] is True
            assert 'latency_ms' in log_data
            assert isinstance(log_data['latency_ms'], int)
            assert 'error' not in log_data

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_redis_connection_error(self, mock_redis_module, client):
        """Test Redis connection error handling"""
        # Mock redis client that raises ConnectionError
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.side_effect = mock_redis_module.ConnectionError("Connection refused")
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check HTTP response
            assert response.status_code == 503
            data = response.get_json()
            assert data['connected'] is False
            assert "redis connection failed" in data['error']
            assert "Connection refused" in data['error']
            
            # Check structured logging
            mock_logger.logger.info.assert_called_once()
            log_call = mock_logger.logger.info.call_args[0][0]
            log_data = json.loads(log_call)
            assert log_data['event'] == "redis_smoke"
            assert log_data['connected'] is False
            assert 'error' in log_data

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_redis_timeout_error(self, mock_redis_module, client):
        """Test Redis timeout error handling"""
        # Mock redis client that raises TimeoutError
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.side_effect = mock_redis_module.TimeoutError("Timeout")
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check HTTP response
            assert response.status_code == 503
            data = response.get_json()
            assert data['connected'] is False
            assert "redis timeout" in data['error']

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_redis_authentication_error(self, mock_redis_module, client):
        """Test Redis authentication error handling"""
        # Mock redis client that raises AuthenticationError
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.side_effect = mock_redis_module.AuthenticationError("Authentication failed")
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check HTTP response
            assert response.status_code == 503
            data = response.get_json()
            assert data['connected'] is False
            assert "redis authentication failed" in data['error']

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_redis_generic_error(self, mock_redis_module, client):
        """Test generic Redis error handling"""
        # Mock redis client that raises generic RedisError
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.side_effect = mock_redis_module.RedisError("Generic Redis error")
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check HTTP response
            assert response.status_code == 503
            data = response.get_json()
            assert data['connected'] is False
            assert "redis error" in data['error']

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_unexpected_error(self, mock_redis_module, client):
        """Test unexpected error handling"""
        # Mock redis client that raises unexpected error
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.side_effect = ValueError("Unexpected error")
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check HTTP response
            assert response.status_code == 503
            data = response.get_json()
            assert data['connected'] is False
            assert "unexpected error" in data['error']
            assert "Unexpected error" in data['error']

    @patch.dict(os.environ, {'REDIS_URL': 'localhost:6379'})  # No protocol prefix
    @patch('app.routes_redis_smoke.redis')
    def test_redis_url_format_handling(self, mock_redis_module, client):
        """Test handling of Redis URL without protocol prefix"""
        # Mock redis client
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.return_value = True
        mock_client.get.return_value = "ok"
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check that redis:// was prepended
            mock_redis_module.from_url.assert_called_once_with(
                'redis://localhost:6379',
                socket_connect_timeout=3,
                socket_timeout=3,
                decode_responses=True
            )
            
            # Check successful response
            assert response.status_code == 200
            data = response.get_json()
            assert data['connected'] is True

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_get_returns_different_value(self, mock_redis_module, client):
        """Test when GET returns different value than what was set"""
        # Mock redis client where GET returns different value
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.return_value = True
        mock_client.get.return_value = "different_value"
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Should still be successful
            assert response.status_code == 200
            data = response.get_json()
            assert data['connected'] is True
            assert data['value'] == "different_value"

    @patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_get_returns_none(self, mock_redis_module, client):
        """Test when GET returns None (key expired or not found)"""
        # Mock redis client where GET returns None
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.return_value = True
        mock_client.get.return_value = None
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Should still be successful
            assert response.status_code == 200
            data = response.get_json()
            assert data['connected'] is True
            assert data['value'] is None

    def test_route_never_raises_exception(self, client):
        """Test that the endpoint never raises unhandled exceptions"""
        # This test ensures all exceptions are caught
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch('app.routes_redis_smoke.redis') as mock_redis_module:
                # Mock an exception that would crash if not handled
                mock_redis_module.from_url.side_effect = Exception("Catastrophic error")
                
                # Should not raise exception, should return 503
                response = client.get('/redis-smoke')
                assert response.status_code == 503
                data = response.get_json()
                assert data['connected'] is False
                assert "unexpected error" in data['error']

    @patch.dict(os.environ, {'REDIS_URL': 'rediss://secure.redis.com:6379'})
    @patch('app.routes_redis_smoke.redis')
    def test_secure_redis_url(self, mock_redis_module, client):
        """Test handling of secure Redis URL (rediss://)"""
        # Mock redis client
        mock_client = Mock()
        mock_redis_module.from_url.return_value = mock_client
        mock_client.set.return_value = True
        mock_client.get.return_value = "ok"
        
        with patch('app.routes_redis_smoke.structured_logger') as mock_logger:
            response = client.get('/redis-smoke')
            
            # Check that rediss:// URL was used as-is
            mock_redis_module.from_url.assert_called_once_with(
                'rediss://secure.redis.com:6379',
                socket_connect_timeout=3,
                socket_timeout=3,
                decode_responses=True
            )
            
            # Check successful response
            assert response.status_code == 200
            data = response.get_json()
            assert data['connected'] is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])