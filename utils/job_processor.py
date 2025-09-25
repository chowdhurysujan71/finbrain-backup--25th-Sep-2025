"""
Job processor for handling queued jobs with circuit breaker integration
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

from .circuit_breaker import circuit_breaker
from .job_queue import Job, job_queue

logger = logging.getLogger(__name__)

class JobProcessor:
    """Process jobs from the queue with circuit breaker protection"""
    
    def __init__(self):
        # Import storage client for result storage
        try:
            from app.storage_supabase import storage_client
            self.storage_client = storage_client
        except ImportError:
            logger.warning("Supabase storage not available for job results")
            self.storage_client = None
        
        # Sentry integration
        self.sentry_enabled = self._init_sentry()
        
        logger.info("Job processor initialized")
    
    def _init_sentry(self) -> bool:
        """Initialize Sentry if configured"""
        try:
            import sentry_sdk
            sentry_dsn = os.getenv('SENTRY_DSN')
            if sentry_dsn:
                logger.info("Sentry integration enabled for job processing")
                return True
        except ImportError:
            pass
        return False
    
    def process_job(self, job: Job) -> bool:
        """
        Process a single job with circuit breaker protection
        
        Args:
            job: Job to process
            
        Returns:
            True if job completed successfully, False if failed
        """
        start_time = time.time()
        request_id = f"job_{job.job_id}_{int(start_time)}"
        
        # Log job start
        self._log_job_event("job_started", job, request_id, 0)
        
        # Add Sentry breadcrumb
        if self.sentry_enabled:
            self._add_sentry_breadcrumb("job_started", job)
        
        try:
            # Check circuit breaker
            if not circuit_breaker.call_allowed():
                error_msg = "Circuit breaker is open - AI service unavailable"
                self._log_job_event("job_circuit_breaker_open", job, request_id, 
                                   (time.time() - start_time) * 1000)
                job_queue.complete_job(job.job_id, False, error=error_msg)
                return False
            
            # Process based on job type
            success, result_path, error = self._process_by_type(job, request_id)
            
            # Record circuit breaker result
            if success:
                circuit_breaker.record_success()
            else:
                # Only record circuit breaker failure for AI-related errors
                if self._is_ai_failure(error):
                    circuit_breaker.record_failure(error)
            
            # Complete job
            job_queue.complete_job(job.job_id, success, result_path, error)
            
            # Log completion
            latency_ms = (time.time() - start_time) * 1000
            event_type = "job_completed" if success else "job_failed"
            self._log_job_event(event_type, job, request_id, latency_ms, result_path, error)
            
            # Add Sentry event for failures
            if not success and self.sentry_enabled:
                self._capture_sentry_error(job, error)
            
            return success
            
        except Exception as e:
            error_msg = f"Job processing exception: {str(e)}"
            latency_ms = (time.time() - start_time) * 1000
            
            # Record circuit breaker failure for unexpected errors
            if self._is_ai_failure(error_msg):
                circuit_breaker.record_failure(error_msg)
            
            # Log error and complete job
            self._log_job_event("job_exception", job, request_id, latency_ms, error=error_msg)
            job_queue.complete_job(job.job_id, False, error=error_msg)
            
            # Capture in Sentry
            if self.sentry_enabled:
                self._capture_sentry_error(job, error_msg, e)
            
            return False
    
    def _process_by_type(self, job: Job, request_id: str) -> tuple[bool, str | None, str | None]:
        """
        Process job based on its type
        
        Returns:
            (success, result_path, error)
        """
        if job.type == "analysis":
            return self._process_analysis_job(job, request_id)
        else:
            return False, None, f"Unknown job type: {job.type}"
    
    def _process_analysis_job(self, job: Job, request_id: str) -> tuple[bool, str | None, str | None]:
        """
        Process analysis job using AI
        
        Returns:
            (success, result_path, error)
        """
        try:
            # Get AI adapter
            from utils.ai_adapter_v2 import production_ai_adapter
            
            # Extract analysis parameters from payload
            text = job.payload.get('text', '')
            analysis_type = job.payload.get('analysis_type', 'general')
            
            if not text:
                return False, None, "Missing 'text' in job payload"
            
            # Perform AI analysis
            start_ai = time.time()
            response = production_ai_adapter.generate_response(
                text, 
                job.user_id, 
                request_id,
                context={"analysis_type": analysis_type}
            )
            ai_latency = (time.time() - start_ai) * 1000
            
            if not response:
                return False, None, "AI adapter returned empty response"
            
            # Store result in Supabase if available
            result_path = None
            if self.storage_client:
                try:
                    result_data = {
                        "job_id": job.job_id,
                        "analysis_type": analysis_type,
                        "input_text": text,
                        "ai_response": response,
                        "ai_latency_ms": ai_latency,
                        "processed_at": datetime.utcnow().isoformat()
                    }
                    
                    # Upload to user's folder
                    file_content = json.dumps(result_data, indent=2)
                    file_path = f"{job.user_id}/analysis_{job.job_id}.json"
                    
                    upload_result = self.storage_client.upload_file_content(
                        file_path, file_content, "application/json"
                    )
                    
                    if upload_result.get("success"):
                        result_path = file_path
                        logger.info(f"Job {job.job_id} result stored at {result_path}")
                    
                except Exception as storage_error:
                    logger.warning(f"Failed to store job result: {storage_error}")
                    # Continue without storage - job still succeeded
            
            return True, result_path, None
            
        except Exception as e:
            error_msg = f"Analysis job failed: {str(e)}"
            logger.error(f"Job {job.job_id} analysis failed: {e}")
            return False, None, error_msg
    
    def _is_ai_failure(self, error: str) -> bool:
        """Check if error is AI-related for circuit breaker"""
        if not error:
            return False
        
        error_lower = error.lower()
        ai_error_indicators = [
            "429",  # Rate limit
            "500",  # Server error
            "timeout",
            "ai adapter",
            "api error",
            "connection",
            "service unavailable"
        ]
        
        return any(indicator in error_lower for indicator in ai_error_indicators)
    
    def _log_job_event(self, event_type: str, job: Job, request_id: str, latency_ms: float,
                       result_path: str | None = None, error: str | None = None) -> None:
        """Log structured job processing event"""
        log_data = {
            "event": event_type,
            "job_id": job.job_id,
            "job_type": job.type,
            "user_id": job.user_id,
            "request_id": request_id,
            "attempt": job.attempts,
            "latency_ms": round(latency_ms, 2),
            "timestamp": time.time()
        }
        
        if result_path:
            log_data["result_path"] = result_path
        if error:
            log_data["error"] = error
        
        logger.info(json.dumps(log_data))
    
    def _add_sentry_breadcrumb(self, action: str, job: Job, extra: dict[str, Any] = None) -> None:
        """Add Sentry breadcrumb for job processing"""
        if not self.sentry_enabled:
            return
        
        try:
            import sentry_sdk
            
            data = {
                "job_id": job.job_id,
                "job_type": job.type,
                "user_id": job.user_id,
                "attempt": job.attempts
            }
            
            if extra:
                data.update(extra)
            
            sentry_sdk.add_breadcrumb(
                message=f"Job {action}",
                category="job_processing",
                level="info",
                data=data
            )
        except Exception as e:
            logger.warning(f"Failed to add Sentry breadcrumb: {e}")
    
    def _capture_sentry_error(self, job: Job, error: str, exception: Exception = None) -> None:
        """Capture job processing error in Sentry"""
        if not self.sentry_enabled:
            return
        
        try:
            import sentry_sdk
            
            with sentry_sdk.configure_scope() as scope:
                scope.set_tag("job_id", job.job_id)
                scope.set_tag("job_type", job.type)
                scope.set_tag("user_id", job.user_id)
                scope.set_context("job", {
                    "job_id": job.job_id,
                    "type": job.type,
                    "user_id": job.user_id,
                    "attempts": job.attempts,
                    "payload": job.payload
                })
                
                if exception:
                    sentry_sdk.capture_exception(exception)
                else:
                    sentry_sdk.capture_message(f"Job processing failed: {error}", level="error")
                    
        except Exception as e:
            logger.warning(f"Failed to capture Sentry error: {e}")

# Global job processor instance
job_processor = JobProcessor()