"""
Redis-backed job queue for FinBrain with idempotency and DLQ support
"""
import os
import json
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class Job:
    """Job definition for queue processing"""
    job_id: str
    type: str
    payload: Dict[str, Any]
    user_id: str
    idempotency_key: str
    status: str  # queued, running, succeeded, failed
    attempts: int
    created_at: float
    updated_at: float
    result_path: Optional[str] = None
    error: Optional[str] = None
    next_retry_at: Optional[float] = None

class JobQueue:
    """Redis-backed job queue with retries and DLQ"""
    
    def __init__(self):
        self.redis_client = None
        self.redis_available = False
        
        # Configuration
        self.job_ttl = 24 * 60 * 60  # 24 hours
        self.dlq_ttl = 7 * 24 * 60 * 60  # 7 days
        self.max_attempts = 3
        self.retry_delays = [1, 5, 30]  # seconds
        
        # Try to initialize Redis, but don't fail if unavailable
        try:
            self._init_redis()
        except Exception as e:
            logger.warning(f"Redis not available for job queue: {e}")
            self.redis_available = False
        
    def _init_redis(self):
        """Initialize Redis connection"""
        import redis
        redis_url = os.getenv('REDIS_URL')
        if not redis_url:
            raise ValueError("REDIS_URL environment variable required")
        
        # Fix malformed Redis URLs
        if redis_url == "rediss:6379":
            logger.warning("Fixing malformed REDIS_URL: rediss:6379 -> redis://localhost:6379")
            redis_url = "redis://localhost:6379"
        elif redis_url.startswith("rediss:") and "://" not in redis_url:
            # Fix incomplete rediss URLs
            redis_url = redis_url.replace("rediss:", "redis://localhost:")
        elif not redis_url.startswith(('redis://', 'rediss://', 'unix://')):
            # Assume it's a plain connection string, prepend redis://
            redis_url = f"redis://{redis_url}"
        
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
            self.redis_client.ping()
            self.redis_available = True
            logger.info(f"Job queue initialized with Redis backend at {redis_url.split('@')[-1]}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
            raise
    
    def enqueue(self, job_type: str, payload: Dict[str, Any], user_id: str, 
                idempotency_key: str) -> str:
        """
        Enqueue a job with idempotency support
        
        Returns:
            job_id: Unique job identifier
        """
        if not self.redis_available:
            raise RuntimeError("Redis job queue not available")
        
        # Check for existing job with same idempotency key
        existing_job_id = self._get_job_by_idempotency_key(idempotency_key)
        if existing_job_id:
            logger.info(f"Job with idempotency_key {idempotency_key} already exists: {existing_job_id}")
            return existing_job_id
        
        # Create new job
        job_id = str(uuid.uuid4())
        now = time.time()
        
        job = Job(
            job_id=job_id,
            type=job_type,
            payload=payload,
            user_id=user_id,
            idempotency_key=idempotency_key,
            status="queued",
            attempts=0,
            created_at=now,
            updated_at=now
        )
        
        # Store job metadata and add to queue
        self._store_job(job)
        self._add_to_queue(job_id)
        self._store_idempotency_key(idempotency_key, job_id)
        
        logger.info(f"Job {job_id} enqueued for user {user_id} with type {job_type}")
        return job_id
    
    def dequeue(self) -> Optional[Job]:
        """
        Dequeue next job for processing
        
        Returns:
            Job or None if queue is empty
        """
        try:
            # Block for up to 1 second waiting for jobs
            result = self.redis_client.blpop("jobs:queue", timeout=1)
            if not result:
                return None
            
            _, job_id = result
            job = self._get_job(job_id)
            
            if not job:
                logger.warning(f"Job {job_id} not found in metadata")
                return None
            
            # Update job status to running
            job.status = "running"
            job.attempts += 1
            job.updated_at = time.time()
            self._store_job(job)
            
            logger.info(f"Job {job_id} dequeued (attempt {job.attempts})")
            return job
            
        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
            return None
    
    def complete_job(self, job_id: str, success: bool, result_path: Optional[str] = None, 
                     error: Optional[str] = None) -> None:
        """
        Mark job as completed (success or failure)
        
        Args:
            job_id: Job identifier
            success: Whether job succeeded
            result_path: Path to result file in storage (if success)
            error: Error message (if failure)
        """
        job = self._get_job(job_id)
        if not job:
            logger.warning(f"Job {job_id} not found for completion")
            return
        
        job.updated_at = time.time()
        
        if success:
            job.status = "succeeded"
            job.result_path = result_path
            logger.info(f"Job {job_id} completed successfully")
        else:
            # Check if we should retry or send to DLQ
            if job.attempts < self.max_attempts:
                # Schedule retry
                delay = self.retry_delays[job.attempts - 1] if job.attempts <= len(self.retry_delays) else 30
                job.next_retry_at = time.time() + delay
                job.status = "queued"
                job.error = error
                
                # Re-add to queue after delay
                self._schedule_retry(job_id, delay)
                logger.info(f"Job {job_id} scheduled for retry {job.attempts}/{self.max_attempts} in {delay}s")
            else:
                # Send to DLQ
                job.status = "failed"
                job.error = error
                self._send_to_dlq(job)
                logger.warning(f"Job {job_id} failed permanently after {job.attempts} attempts")
        
        self._store_job(job)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and metadata"""
        job = self._get_job(job_id)
        if not job:
            return None
        
        return {
            "job_id": job.job_id,
            "status": job.status,
            "attempts": job.attempts,
            "result_path": job.result_path,
            "error": job.error,
            "created_at": job.created_at,
            "updated_at": job.updated_at
        }
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job (best effort)
        
        Returns:
            True if job was cancelled or already completed
        """
        job = self._get_job(job_id)
        if not job:
            return False
        
        if job.status in ["succeeded", "failed"]:
            return True  # Already completed
        
        if job.status == "running":
            # Can't cancel running job, but mark for cancellation
            logger.warning(f"Job {job_id} is running, cannot cancel")
            return False
        
        # Remove from queue and mark as failed
        job.status = "failed"
        job.error = "Cancelled by user"
        job.updated_at = time.time()
        self._store_job(job)
        
        logger.info(f"Job {job_id} cancelled")
        return True
    
    def _store_job(self, job: Job) -> None:
        """Store job metadata in Redis"""
        key = f"jobs:meta:{job.job_id}"
        data = json.dumps(asdict(job))
        self.redis_client.setex(key, self.job_ttl, data)
    
    def _get_job(self, job_id: str) -> Optional[Job]:
        """Get job metadata from Redis"""
        key = f"jobs:meta:{job_id}"
        data = self.redis_client.get(key)
        if not data:
            return None
        
        job_dict = json.loads(data)
        return Job(**job_dict)
    
    def _add_to_queue(self, job_id: str) -> None:
        """Add job to Redis queue"""
        self.redis_client.rpush("jobs:queue", job_id)
    
    def _schedule_retry(self, job_id: str, delay: int) -> None:
        """Schedule job retry after delay"""
        # Use Redis sorted set for delayed jobs
        retry_time = time.time() + delay
        self.redis_client.zadd("jobs:retry", {job_id: retry_time})
    
    def _send_to_dlq(self, job: Job) -> None:
        """Send failed job to dead letter queue"""
        dlq_data = {
            "job_id": job.job_id,
            "type": job.type,
            "user_id": job.user_id,
            "payload": job.payload,
            "error": job.error,
            "attempts": job.attempts,
            "failed_at": time.time()
        }
        
        # Store in DLQ with longer TTL
        dlq_key = f"jobs:dlq:{job.job_id}"
        self.redis_client.setex(dlq_key, self.dlq_ttl, json.dumps(dlq_data))
        
        # Add to DLQ list for monitoring
        self.redis_client.rpush("jobs:dlq:list", job.job_id)
    
    def _store_idempotency_key(self, idempotency_key: str, job_id: str) -> None:
        """Store idempotency key mapping"""
        key = f"jobs:idem:{idempotency_key}"
        self.redis_client.setex(key, self.job_ttl, job_id)
    
    def _get_job_by_idempotency_key(self, idempotency_key: str) -> Optional[str]:
        """Get job ID by idempotency key"""
        key = f"jobs:idem:{idempotency_key}"
        return self.redis_client.get(key)
    
    def process_retry_queue(self) -> List[str]:
        """
        Process retry queue and move ready jobs back to main queue
        
        Returns:
            List of job IDs that were moved to main queue
        """
        now = time.time()
        
        # Get jobs ready for retry
        ready_jobs = self.redis_client.zrangebyscore("jobs:retry", 0, now)
        
        if ready_jobs:
            # Remove from retry queue and add back to main queue
            for job_id in ready_jobs:
                self.redis_client.zrem("jobs:retry", job_id)
                self._add_to_queue(job_id)
                logger.info(f"Job {job_id} moved from retry queue to main queue")
        
        return ready_jobs
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        return {
            "queued": self.redis_client.llen("jobs:queue"),
            "retry": self.redis_client.zcard("jobs:retry"),
            "dlq": self.redis_client.llen("jobs:dlq:list")
        }
    
    def health_check(self) -> bool:
        """Check Redis connectivity"""
        if not self.redis_available or not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False

# Global job queue instance
job_queue = JobQueue()