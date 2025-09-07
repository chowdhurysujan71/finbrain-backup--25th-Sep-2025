"""
Phase C UAT: Redis Job Queue, Retries, DLQ, and Circuit Breaker

Comprehensive User Acceptance Testing for Phase C implementation covering:
- Happy path job processing
- Retry logic with exponential backoff  
- Dead Letter Queue (DLQ) population
- Idempotency key handling
- Rate limiting enforcement
- Circuit breaker state transitions
- Redis failure graceful degradation

All tests use mocking to avoid external dependencies and enable fast execution.
"""

import os
import time
import json
import uuid
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from dataclasses import asdict

import redis
from flask import Flask

# Import the components we're testing
from utils.job_queue import JobQueue, Job, job_queue
from utils.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerConfig
from utils.rate_limiter_jobs import JobRateLimiter, RateLimitResult
from utils.job_processor import JobProcessor


class TestPhaseC_HappyPath:
    """Test happy path: job creation → processing → success → result storage"""
    
    def test_happy_path_job_lifecycle(self):
        """Test complete happy path: enqueue → process → store result → query status"""
        # Create queue and mock Redis after initialization
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch('redis.from_url') as mock_redis_from_url:
                # Setup mock Redis client
                mock_redis = Mock()
                mock_redis.ping.return_value = True
                mock_redis.get.return_value = None  # No existing idempotency
                mock_redis.setex.return_value = True
                mock_redis.rpush.return_value = 1
                mock_redis.blpop.return_value = ('jobs:queue', 'test-job-123')
                
                mock_redis_from_url.return_value = mock_redis
                
                # Mock job metadata
                test_job = Job(
                    job_id="test-job-123",
                    type="analysis", 
                    payload={"text": "test message", "analysis_type": "sentiment"},
                    user_id="test-user",
                    idempotency_key="test-key-1",
                    status="queued",
                    attempts=0,
                    created_at=time.time(),
                    updated_at=time.time()
                )
                
                # Setup Redis responses for different calls
                redis_responses = [
                    None,  # Idempotency check
                    json.dumps(asdict(test_job)),  # Job retrieval for dequeue
                    json.dumps({**asdict(test_job), "status": "running", "attempts": 1}),  # After dequeue
                    json.dumps({**asdict(test_job), "status": "succeeded", "result_path": "test-user/analysis_test-job-123.json"})
                ]
                mock_redis.get.side_effect = redis_responses
                
                # Create job queue
                queue = JobQueue()
                assert queue.redis_available is True
                
                # Test enqueue
                with patch('uuid.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-123456789abc')):
                    job_id = queue.enqueue("analysis", {"text": "test message"}, "test-user", "test-key-1")
                    assert job_id == "12345678-1234-5678-1234-123456789abc"
                
                # Test dequeue
                dequeued_job = queue.dequeue()
                assert dequeued_job is not None
                assert dequeued_job.job_id == "test-job-123"
                
                # Test completion
                queue.complete_job("test-job-123", True, "test-user/analysis_test-job-123.json")
                
                # Test status retrieval
                status = queue.get_job_status("test-job-123")
                assert status["job_id"] == "test-job-123"
                assert status["status"] == "succeeded"


class TestPhaseC_Retries:
    """Test retry logic with exponential backoff and DLQ population"""
    
    def test_job_retries_with_backoff_then_dlq(self):
        """Test job fails 3 times with proper retry delays, then goes to DLQ"""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch('redis.from_url') as mock_redis_from_url:
                mock_redis = Mock()
                mock_redis.ping.return_value = True
                mock_redis.zadd.return_value = 1
                mock_redis.rpush.return_value = 1
                mock_redis.setex.return_value = True
                
                mock_redis_from_url.return_value = mock_redis
                
                # Mock job progression through attempts
                test_job = Job(
                    job_id="retry-job-456",
                    type="analysis",
                    payload={"text": "failing job"},
                    user_id="retry-user", 
                    idempotency_key="retry-key",
                    status="running",
                    attempts=1,
                    created_at=time.time(),
                    updated_at=time.time()
                )
                
                mock_redis.get.return_value = json.dumps(asdict(test_job))
                
                queue = JobQueue()
                
                # Test retry scheduling with proper delays
                with patch('time.time', return_value=1000.0):
                    # First failure - should schedule retry with 1s delay
                    queue.complete_job("retry-job-456", False, error="Timeout error")
                    mock_redis.zadd.assert_called_with("jobs:retry", {"retry-job-456": 1001.0})
                    
                    # Update job for second attempt
                    test_job.attempts = 2
                    mock_redis.get.return_value = json.dumps(asdict(test_job))
                    
                    # Second failure - should schedule retry with 5s delay  
                    queue.complete_job("retry-job-456", False, error="Connection error")
                    mock_redis.zadd.assert_called_with("jobs:retry", {"retry-job-456": 1005.0})
                    
                    # Update job for third attempt
                    test_job.attempts = 3
                    mock_redis.get.return_value = json.dumps(asdict(test_job))
                    
                    # Third failure - should go to DLQ
                    queue.complete_job("retry-job-456", False, error="AI service error 500")
                    
                    # Verify DLQ operations
                    mock_redis.rpush.assert_called_with("jobs:dlq:list", "retry-job-456")
                    assert mock_redis.setex.call_count >= 4  # Job updates + DLQ metadata


class TestPhaseC_Idempotency:
    """Test idempotency key handling returns same job_id"""
    
    def test_same_idempotency_key_returns_existing_job(self):
        """Test that same idempotency key returns existing job_id"""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch('redis.from_url') as mock_redis_from_url:
                mock_redis = Mock()
                mock_redis.ping.return_value = True
                
                # First call: no existing job, second call: existing job
                mock_redis.get.side_effect = [None, "existing-job-789"]
                mock_redis.setex.return_value = True
                mock_redis.rpush.return_value = 1
                
                mock_redis_from_url.return_value = mock_redis
                
                queue = JobQueue()
                
                with patch('uuid.uuid4', return_value=uuid.UUID('12345678-1234-5678-1234-123456789abc')):
                    # First enqueue - creates new job
                    job_id_1 = queue.enqueue("analysis", {"text": "test"}, "user-1", "idem-key-1")
                    assert job_id_1 == "12345678-1234-5678-1234-123456789abc"
                    
                    # Second enqueue with same idempotency key - returns existing job
                    job_id_2 = queue.enqueue("analysis", {"text": "different text"}, "user-1", "idem-key-1") 
                    assert job_id_2 == "existing-job-789"


class TestPhaseC_RateLimit:
    """Test rate limiting: >60 jobs/hour returns 429"""
    
    def test_rate_limit_enforcement(self):
        """Test rate limiting blocks requests after 60 jobs/hour"""
        # Setup mock Redis with pipeline
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        # Mock pipeline operations - simulate 60 existing requests
        mock_pipeline.execute.return_value = [None, 60, None, None]  # [cleanup, count, add, expire]
        
        with patch('time.time', return_value=1000.0):
            limiter = JobRateLimiter(mock_redis)
            
            # Test limit enforcement
            result = limiter.check_rate_limit("heavy-user")
            
            assert result.allowed is False
            assert result.remaining == 0
            assert "Rate limit exceeded" in result.reason
            assert result.reset_time == 1000.0 + 3600  # 1 hour window
    
    def test_rate_limit_allows_within_limit(self):
        """Test rate limiting allows requests within limit"""
        mock_redis = Mock()
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        # Mock pipeline - simulate 30 existing requests (within limit)
        mock_pipeline.execute.return_value = [None, 30, None, None]
        
        with patch('time.time', return_value=2000.0):
            limiter = JobRateLimiter(mock_redis)
            
            result = limiter.check_rate_limit("normal-user")
            
            assert result.allowed is True
            assert result.remaining == 29  # 60 - 30 - 1 for current request
            assert result.reason is None


class TestPhaseC_CircuitBreaker:
    """Test circuit breaker: >5 failures opens circuit, blocks requests, half-open recovery"""
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit opens after 5 failures in 60s window"""
        with patch('utils.circuit_breaker.time.time') as mock_time:
            mock_time.return_value = 1000.0
            
            breaker = CircuitBreaker()
            
            # Record 4 failures - should stay closed
            for i in range(4):
                breaker.record_failure(f"Error {i+1}")
                assert breaker.state == CircuitState.CLOSED
                assert breaker.call_allowed() is True
            
            # 5th failure should open circuit
            breaker.record_failure("Final error")
            assert breaker.state == CircuitState.OPEN
            assert breaker.call_allowed() is False
            assert breaker.is_open() is True
    
    def test_circuit_breaker_half_open_transition(self):
        """Test circuit transitions to half-open after timeout, then closes on success"""
        with patch('utils.circuit_breaker.time.time') as mock_time:
            mock_time.return_value = 1000.0
            
            breaker = CircuitBreaker()
            
            # Force circuit open
            for i in range(5):
                breaker.record_failure(f"Error {i+1}")
            assert breaker.state == CircuitState.OPEN
            
            # Time passes, but not enough for half-open
            mock_time.return_value = 1020.0  # 20 seconds later
            assert breaker.call_allowed() is False
            
            # After 30+ seconds, should transition to half-open
            mock_time.return_value = 1035.0  # 35 seconds later  
            assert breaker.call_allowed() is True
            assert breaker.state == CircuitState.HALF_OPEN
            
            # Success in half-open should close circuit
            breaker.record_success()
            assert breaker.state == CircuitState.CLOSED
            assert breaker.call_allowed() is True
    
    def test_circuit_breaker_failure_in_half_open_reopens(self):
        """Test failure in half-open state reopens circuit"""
        with patch('utils.circuit_breaker.time.time') as mock_time:
            mock_time.return_value = 1000.0
            
            breaker = CircuitBreaker()
            
            # Open circuit
            for i in range(5):
                breaker.record_failure(f"Error {i+1}")
            
            # Transition to half-open
            mock_time.return_value = 1040.0
            assert breaker.call_allowed() is True
            assert breaker.state == CircuitState.HALF_OPEN
            
            # Failure should reopen circuit
            breaker.record_failure("Half-open failure")
            assert breaker.state == CircuitState.OPEN
            assert breaker.call_allowed() is False


class TestPhaseC_RedisDown:
    """Test graceful degradation when Redis is unavailable"""
    
    def test_job_enqueue_fails_gracefully_when_redis_down(self):
        """Test job enqueue returns error when Redis unavailable"""
        # Create queue with no REDIS_URL
        with patch.dict(os.environ, {}, clear=True):
            queue = JobQueue()
            assert queue.redis_available is False
            
            # Enqueue should raise RuntimeError
            with pytest.raises(RuntimeError, match="Redis job queue not available"):
                queue.enqueue("analysis", {"text": "test"}, "user", "key")
    
    def test_job_status_fails_gracefully_when_redis_down(self):
        """Test job status returns None when Redis unavailable"""
        with patch.dict(os.environ, {}, clear=True):
            queue = JobQueue()
            assert queue.redis_available is False
            
            # Status check should return None gracefully
            status = queue.get_job_status("nonexistent-job")
            assert status is None
    
    def test_rate_limiter_fails_open_when_redis_down(self):
        """Test rate limiter allows requests when Redis fails"""
        limiter = JobRateLimiter(redis_client=None)  # No Redis
        
        result = limiter.check_rate_limit("any-user")
        
        assert result.allowed is True
        assert result.reason is None
        assert result.remaining == 60  # Default limit


class TestPhaseC_JobProcessorIntegration:
    """Test job processor with circuit breaker integration"""
    
    def test_job_processor_respects_circuit_breaker(self):
        """Test job processor skips processing when circuit is open"""
        test_job = Job(
            job_id="blocked-job",
            type="analysis",
            payload={"text": "test"},
            user_id="user",
            idempotency_key="key",
            status="running", 
            attempts=1,
            created_at=time.time(),
            updated_at=time.time()
        )
        
        # Mock circuit breaker as open
        mock_breaker = Mock()
        mock_breaker.call_allowed.return_value = False
        
        # Mock job queue
        mock_queue = Mock()
        
        with patch('utils.job_processor.circuit_breaker', mock_breaker):
            with patch('utils.job_processor.job_queue', mock_queue):
                processor = JobProcessor()
                
                result = processor.process_job(test_job)
                
                assert result is False
                mock_queue.complete_job.assert_called_with(
                    "blocked-job", 
                    False, 
                    error="Circuit breaker is open - AI service unavailable"
                )
    
    def test_job_processor_ai_success_closes_circuit(self):
        """Test successful AI processing records circuit breaker success"""
        test_job = Job(
            job_id="success-job",
            type="analysis",
            payload={"text": "analyze this"},
            user_id="user",
            idempotency_key="key",
            status="running",
            attempts=1, 
            created_at=time.time(),
            updated_at=time.time()
        )
        
        # Mock successful AI response
        mock_ai_adapter = Mock()
        mock_ai_adapter.generate_response.return_value = "Analysis result: positive sentiment"
        
        mock_breaker = Mock()
        mock_breaker.call_allowed.return_value = True
        
        mock_queue = Mock()
        mock_storage = Mock()
        mock_storage.upload_file_content.return_value = {"success": True}
        
        with patch('utils.job_processor.circuit_breaker', mock_breaker):
            with patch('utils.job_processor.job_queue', mock_queue):
                with patch('utils.ai_adapter_v2.production_ai_adapter', mock_ai_adapter):
                    processor = JobProcessor()
                    processor.storage_client = mock_storage
                    
                    result = processor.process_job(test_job)
                    
                    assert result is True
                    mock_breaker.record_success.assert_called_once()
                    mock_queue.complete_job.assert_called_with(
                        "success-job",
                        True,
                        "user/analysis_success-job.json",
                        None
                    )


class TestPhaseC_TimeControls:
    """Test time-dependent behaviors with mocked time"""
    
    def test_retry_queue_processing_with_time_control(self):
        """Test retry queue processes jobs when retry time arrives"""
        with patch.dict(os.environ, {'REDIS_URL': 'redis://localhost:6379'}):
            with patch('redis.from_url') as mock_redis_from_url:
                mock_redis = Mock()
                mock_redis.ping.return_value = True
                mock_redis.zrangebyscore.return_value = ['retry-job-1', 'retry-job-2']
                mock_redis.zrem.return_value = 1
                mock_redis.rpush.return_value = 1
                
                mock_redis_from_url.return_value = mock_redis
                
                with patch('time.time', return_value=1000.0):
                    queue = JobQueue()
                    
                    # Process retry queue
                    moved_jobs = queue.process_retry_queue()
                    
                    assert moved_jobs == ['retry-job-1', 'retry-job-2']
                    
                    # Verify jobs moved from retry to main queue
                    mock_redis.zrangebyscore.assert_called_with("jobs:retry", 0, 1000.0)
                    assert mock_redis.zrem.call_count == 2
                    assert mock_redis.rpush.call_count == 2


class TestPhaseC_APIValidation:
    """Test API endpoint validation and error handling"""
    
    def test_job_api_validation_missing_fields(self):
        """Test job API validates required fields"""
        from app import app
        
        with app.test_client() as client:
            # Missing X-User-ID header
            response = client.post('/jobs', json={"type": "analysis", "idempotency_key": "test"})
            assert response.status_code == 400
            assert "X-User-ID header required" in response.get_json()["error"]
            
            # Missing type field
            response = client.post('/jobs', 
                                 json={"idempotency_key": "test"},
                                 headers={"X-User-ID": "testuser"})
            assert response.status_code == 400
            assert "Field 'type' is required" in response.get_json()["error"]
            
            # Missing idempotency_key
            response = client.post('/jobs',
                                 json={"type": "analysis"},
                                 headers={"X-User-ID": "testuser"})
            assert response.status_code == 400
            assert "Field 'idempotency_key' is required" in response.get_json()["error"]
    
    def test_job_status_api_requires_user_header(self):
        """Test job status API requires X-User-ID header"""
        from app import app
        
        with app.test_client() as client:
            response = client.get('/jobs/test-job-id/status')
            assert response.status_code == 400
            assert "X-User-ID header required" in response.get_json()["error"]


# UAT execution metrics and reporting
class UATMetrics:
    """Collect and report UAT execution metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.test_results = {}
        self.performance_metrics = {}
    
    def record_test(self, test_name: str, passed: bool, duration_ms: float):
        """Record individual test result"""
        self.test_results[test_name] = {
            "passed": passed,
            "duration_ms": duration_ms
        }
    
    def record_performance(self, operation: str, latency_ms: float):
        """Record performance metric"""
        if operation not in self.performance_metrics:
            self.performance_metrics[operation] = []
        self.performance_metrics[operation].append(latency_ms)
    
    def generate_report(self) -> dict:
        """Generate comprehensive UAT report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result["passed"])
        
        # Calculate p95 latencies
        p95_metrics = {}
        for op, latencies in self.performance_metrics.items():
            if latencies:
                sorted_latencies = sorted(latencies)
                p95_index = int(0.95 * len(sorted_latencies))
                p95_metrics[op] = sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else sorted_latencies[-1]
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": total_tests - passed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%",
                "execution_time_ms": (time.time() - self.start_time) * 1000
            },
            "performance": {
                "p95_latencies": p95_metrics,
                "operations_tested": list(self.performance_metrics.keys())
            },
            "test_results": self.test_results
        }


if __name__ == "__main__":
    """Run UAT when executed directly"""
    print("🚀 Starting Phase C UAT - Redis Queue, Retries, DLQ, Circuit Breaker")
    
    metrics = UATMetrics()
    
    # Record mock performance metrics for demonstration
    metrics.record_performance("job_enqueue", 15.2)
    metrics.record_performance("job_enqueue", 18.7) 
    metrics.record_performance("job_enqueue", 12.3)
    metrics.record_performance("circuit_breaker_check", 0.8)
    metrics.record_performance("rate_limit_check", 2.1)
    
    print("✅ Phase C UAT test suite ready for execution")
    print("Run with: pytest tests/test_phase_c_uat.py -v")