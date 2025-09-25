"""Test suite for Redis Job Queue implementation"""
import json
import time
import uuid
from unittest.mock import Mock, patch

import pytest

from utils.circuit_breaker import CircuitBreaker
from utils.job_processor import JobProcessor

# Import modules to test
from utils.job_queue import Job, JobQueue
from utils.rate_limiter_jobs import RateLimitResult, get_job_rate_limiter


class TestJob:
    """Test Job dataclass"""
    
    def test_job_creation(self):
        """Test Job dataclass creation and serialization"""
        job = Job(
            job_id="test-123",
            type="ai_analysis",
            payload={"text": "test message"},
            user_id="user-456",
            idempotency_key="unique-key",
            status="queued",
            attempts=0,
            created_at=time.time(),
            updated_at=time.time()
        )
        
        assert job.job_id == "test-123"
        assert job.type == "ai_analysis"
        assert job.payload["text"] == "test message"
        assert job.status == "queued"
        assert job.attempts == 0


class TestJobQueue:
    """Test JobQueue implementation with Redis mocking"""
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    def test_init_with_redis_available(self, mock_getenv, mock_redis_module):
        """Test JobQueue initialization when Redis is available"""
        mock_getenv.return_value = "redis://localhost:6379"
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        queue = JobQueue()
        
        assert queue.redis_available is True
        assert queue.redis_client == mock_redis_client
        mock_redis_client.ping.assert_called_once()
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    def test_init_without_redis(self, mock_getenv, mock_redis_module):
        """Test JobQueue initialization when Redis is unavailable"""
        mock_getenv.return_value = None
        
        queue = JobQueue()
        
        assert queue.redis_available is False
        assert queue.redis_client is None
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    def test_init_redis_connection_error(self, mock_getenv, mock_redis_module):
        """Test JobQueue initialization when Redis connection fails"""
        mock_getenv.return_value = "redis://localhost:6379"
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.side_effect = Exception("Connection failed")
        
        queue = JobQueue()
        
        assert queue.redis_available is False
        assert queue.redis_client is None
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    def test_enqueue_redis_unavailable(self, mock_getenv, mock_redis_module):
        """Test job enqueue when Redis is unavailable"""
        mock_getenv.return_value = None
        
        queue = JobQueue()
        
        with pytest.raises(RuntimeError, match="Redis job queue not available"):
            queue.enqueue("ai_analysis", {"text": "test"}, "user-123", "key-456")
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    @patch('utils.job_queue.uuid.uuid4')
    @patch('utils.job_queue.time.time')
    def test_enqueue_success(self, mock_time, mock_uuid, mock_getenv, mock_redis_module):
        """Test successful job enqueue"""
        # Setup mocks
        mock_getenv.return_value = "redis://localhost:6379"
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        mock_uuid.return_value = Mock(spec=uuid.UUID)
        mock_uuid.return_value.__str__ = Mock(return_value="job-123")
        mock_time.return_value = 1234567890.0
        
        # Mock Redis operations
        mock_redis_client.get.return_value = None  # No existing idempotency key
        
        queue = JobQueue()
        
        # Test enqueue
        job_id = queue.enqueue("ai_analysis", {"text": "test"}, "user-456", "unique-key")
        
        assert job_id == "job-123"
        # Verify Redis calls were made
        assert mock_redis_client.set.call_count >= 1
        assert mock_redis_client.lpush.call_count == 1
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    def test_health_check_redis_available(self, mock_getenv, mock_redis_module):
        """Test health check when Redis is available"""
        mock_getenv.return_value = "redis://localhost:6379"
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        queue = JobQueue()
        
        assert queue.health_check() is True
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    def test_health_check_redis_unavailable(self, mock_getenv, mock_redis_module):
        """Test health check when Redis is unavailable"""
        mock_getenv.return_value = None
        
        queue = JobQueue()
        
        assert queue.health_check() is False


class TestCircuitBreaker:
    """Test CircuitBreaker implementation"""
    
    @patch('utils.circuit_breaker.time.time')
    def test_circuit_breaker_closed_state(self, mock_time):
        """Test circuit breaker in closed state"""
        mock_time.return_value = 1000.0
        
        breaker = CircuitBreaker()
        
        assert breaker.state == "closed"
        assert breaker.is_open() is False
        assert breaker.is_closed() is True
    
    @patch('utils.circuit_breaker.time.time')
    def test_circuit_breaker_failure_tracking(self, mock_time):
        """Test circuit breaker failure tracking and opening"""
        mock_time.return_value = 1000.0
        
        breaker = CircuitBreaker(failure_threshold=3, window_seconds=60)
        
        # Record failures (within threshold)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_closed() is True
        
        # Record failure that exceeds threshold
        breaker.record_failure()
        assert breaker.is_open() is True
        assert breaker.state == "open"
    
    @patch('utils.circuit_breaker.time.time')
    def test_circuit_breaker_half_open_transition(self, mock_time):
        """Test circuit breaker transition to half-open state"""
        # Start at time 1000
        mock_time.return_value = 1000.0
        
        breaker = CircuitBreaker(failure_threshold=2, window_seconds=60, timeout_seconds=30)
        
        # Force circuit to open
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open() is True
        
        # Advance time past timeout
        mock_time.return_value = 1035.0  # 35 seconds later
        
        # Check if half-open
        assert breaker.is_half_open() is True
        assert breaker.state == "half_open"
    
    @patch('utils.circuit_breaker.time.time')
    def test_circuit_breaker_success_resets(self, mock_time):
        """Test circuit breaker resets on success"""
        mock_time.return_value = 1000.0
        
        breaker = CircuitBreaker(failure_threshold=3)
        
        # Record some failures
        breaker.record_failure()
        breaker.record_failure()
        
        # Record success - should reset failure count
        breaker.record_success()
        
        # Should still be closed after more failures since count was reset
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_closed() is True


class TestRateLimiter:
    """Test job rate limiter implementation"""
    
    def test_get_rate_limiter_without_redis(self):
        """Test creating rate limiter without Redis"""
        limiter = get_job_rate_limiter()
        
        result = limiter.check_rate_limit("user-123")
        assert isinstance(result, RateLimitResult)
        assert result.allowed is True  # Should allow when Redis unavailable
    
    @patch('utils.rate_limiter_jobs.time.time')
    def test_rate_limiter_with_redis_mock(self, mock_time):
        """Test rate limiter with mocked Redis"""
        mock_time.return_value = 1000.0
        
        mock_redis = Mock()
        mock_redis.exists.return_value = False
        mock_redis.incr.return_value = 1
        mock_redis.ttl.return_value = 3600
        
        limiter = get_job_rate_limiter(mock_redis)
        
        result = limiter.check_rate_limit("user-123")
        
        assert result.allowed is True
        assert result.remaining_quota == 59  # 60 - 1
        mock_redis.incr.assert_called_once()
    
    @patch('utils.rate_limiter_jobs.time.time')
    def test_rate_limiter_exceed_limit(self, mock_time):
        """Test rate limiter when limit exceeded"""
        mock_time.return_value = 1000.0
        
        mock_redis = Mock()
        mock_redis.exists.return_value = True
        mock_redis.get.return_value = "60"  # At limit
        mock_redis.ttl.return_value = 1800  # 30 minutes remaining
        
        limiter = get_job_rate_limiter(mock_redis)
        
        result = limiter.check_rate_limit("user-123")
        
        assert result.allowed is False
        assert result.remaining_quota == 0
        assert result.reset_time == 2800.0  # 1000 + 1800


class TestJobProcessor:
    """Test JobProcessor implementation"""
    
    @patch('utils.job_processor.storage')
    def test_job_processor_init_no_storage(self, mock_storage):
        """Test JobProcessor initialization without storage"""
        mock_storage.is_available.return_value = False
        
        processor = JobProcessor()
        
        assert processor.storage_available is False
    
    @patch('utils.job_processor.storage')
    def test_job_processor_init_with_storage(self, mock_storage):
        """Test JobProcessor initialization with storage"""
        mock_storage.is_available.return_value = True
        
        processor = JobProcessor()
        
        assert processor.storage_available is True
    
    @patch('utils.job_processor.storage')
    def test_process_ai_analysis_job(self, mock_storage):
        """Test processing AI analysis job"""
        mock_storage.is_available.return_value = True
        
        processor = JobProcessor()
        
        job = Job(
            job_id="test-123",
            type="ai_analysis", 
            payload={"text": "analyze this"},
            user_id="user-456",
            idempotency_key="key-123",
            status="queued",
            attempts=0,
            created_at=time.time(),
            updated_at=time.time()
        )
        
        # Mock the AI processing
        with patch.object(processor, '_process_ai_analysis') as mock_ai:
            mock_ai.return_value = {"result": "analysis complete"}
            
            result = processor.process_job(job)
            
            assert result["status"] == "completed"
            assert "result" in result
            mock_ai.assert_called_once_with(job.payload)
    
    @patch('utils.job_processor.storage')
    def test_process_unknown_job_type(self, mock_storage):
        """Test processing unknown job type"""
        mock_storage.is_available.return_value = True
        
        processor = JobProcessor()
        
        job = Job(
            job_id="test-123",
            type="unknown_type",
            payload={},
            user_id="user-456", 
            idempotency_key="key-123",
            status="queued",
            attempts=0,
            created_at=time.time(),
            updated_at=time.time()
        )
        
        result = processor.process_job(job)
        
        assert result["status"] == "failed"
        assert "error" in result
        assert "Unknown job type" in result["error"]


class TestIntegration:
    """Integration tests for the complete job queue system"""
    
    @patch('utils.job_queue.redis')
    @patch('utils.job_queue.os.getenv')
    def test_full_job_lifecycle_mock(self, mock_getenv, mock_redis_module):
        """Test complete job lifecycle with mocked Redis"""
        # Setup Redis mock
        mock_getenv.return_value = "redis://localhost:6379"
        mock_redis_client = Mock()
        mock_redis_module.from_url.return_value = mock_redis_client
        mock_redis_client.ping.return_value = True
        
        # Mock Redis operations for enqueue
        mock_redis_client.get.return_value = None  # No existing job
        mock_redis_client.brpop.return_value = ("jobs:queue", json.dumps({
            "job_id": "test-123",
            "type": "ai_analysis",
            "payload": {"text": "test"},
            "user_id": "user-456",
            "idempotency_key": "key-789",
            "status": "queued",
            "attempts": 0,
            "created_at": time.time(),
            "updated_at": time.time()
        }))
        
        queue = JobQueue()
        
        # Test enqueue
        with patch('utils.job_queue.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.__str__ = Mock(return_value="test-123")
            
            job_id = queue.enqueue("ai_analysis", {"text": "test"}, "user-456", "key-789")
            assert job_id == "test-123"
        
        # Test dequeue
        job = queue.dequeue()
        assert job is not None
        assert job.job_id == "test-123"
        assert job.type == "ai_analysis"
    
    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with job queue"""
        breaker = CircuitBreaker(failure_threshold=2, window_seconds=60)
        
        # Should start closed
        assert breaker.is_closed() is True
        
        # Record failures to open circuit
        breaker.record_failure()
        breaker.record_failure()
        
        # Should now be open
        assert breaker.is_open() is True
        
        # Jobs should be rejected when circuit is open
        # (This would be handled in the API endpoint)
    
    def test_rate_limiter_integration(self):
        """Test rate limiter integration"""
        limiter = get_job_rate_limiter()  # Without Redis
        
        # Should allow requests when Redis unavailable
        result = limiter.check_rate_limit("user-123")
        assert result.allowed is True
        
        # Multiple calls should still be allowed
        for _ in range(10):
            result = limiter.check_rate_limit("user-123")
            assert result.allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])