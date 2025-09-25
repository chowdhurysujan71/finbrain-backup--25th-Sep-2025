"""
Circuit breaker for AI provider failures
"""
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5  # failures in window to open
    window_seconds: int = 60    # rolling window for failures
    timeout_seconds: int = 30   # time to wait before half-open
    max_half_open_attempts: int = 1  # requests in half-open state

class CircuitBreaker:
    """Circuit breaker for AI provider failures"""
    
    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.last_state_change = time.time()
        self.half_open_attempts = 0
        
        # Rolling window for failures
        self.failure_times = []
        
        logger.info(f"Circuit breaker initialized: threshold={self.config.failure_threshold}, "
                   f"window={self.config.window_seconds}s, timeout={self.config.timeout_seconds}s")
    
    def call_allowed(self) -> bool:
        """
        Check if calls are allowed through the circuit breaker
        
        Returns:
            True if call is allowed, False if circuit is open
        """
        current_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            return True
        
        elif self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if current_time - self.last_state_change >= self.config.timeout_seconds:
                self._transition_to_half_open()
                return True
            return False
        
        elif self.state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open state
            if self.half_open_attempts < self.config.max_half_open_attempts:
                self.half_open_attempts += 1
                return True
            return False
        
        return False
    
    def record_success(self) -> None:
        """Record successful call"""
        if self.state == CircuitState.HALF_OPEN:
            # Success in half-open means we can close the circuit
            self._transition_to_closed()
            logger.info("Circuit breaker closed after successful half-open request")
        
        # Clear old failures for closed circuit
        if self.state == CircuitState.CLOSED:
            self._clean_old_failures()
    
    def record_failure(self, error: str | None = None) -> None:
        """Record failed call"""
        current_time = time.time()
        self.failure_times.append(current_time)
        self.last_failure_time = current_time
        
        # Clean old failures outside window
        self._clean_old_failures()
        
        # Count failures in current window
        window_failures = len(self.failure_times)
        
        logger.warning(f"Circuit breaker recorded failure: {error or 'unknown'} "
                      f"({window_failures}/{self.config.failure_threshold} in window)")
        
        if self.state == CircuitState.CLOSED:
            if window_failures >= self.config.failure_threshold:
                self._transition_to_open()
        
        elif self.state == CircuitState.HALF_OPEN:
            # Failure in half-open means go back to open
            self._transition_to_open()
    
    def _transition_to_open(self) -> None:
        """Transition to open state"""
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()
        self.half_open_attempts = 0
        logger.warning(f"Circuit breaker opened due to {len(self.failure_times)} failures")
    
    def _transition_to_half_open(self) -> None:
        """Transition to half-open state"""
        self.state = CircuitState.HALF_OPEN
        self.last_state_change = time.time()
        self.half_open_attempts = 0
        logger.info("Circuit breaker transitioned to half-open")
    
    def _transition_to_closed(self) -> None:
        """Transition to closed state"""
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()
        self.half_open_attempts = 0
        self.failure_times.clear()
        logger.info("Circuit breaker closed")
    
    def _clean_old_failures(self) -> None:
        """Remove failures outside the rolling window"""
        current_time = time.time()
        cutoff_time = current_time - self.config.window_seconds
        self.failure_times = [t for t in self.failure_times if t > cutoff_time]
    
    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status"""
        self._clean_old_failures()
        current_time = time.time()
        
        return {
            "state": self.state.value,
            "failure_count_in_window": len(self.failure_times),
            "failure_threshold": self.config.failure_threshold,
            "window_seconds": self.config.window_seconds,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": current_time - self.last_failure_time if self.last_failure_time else None,
            "time_in_current_state": current_time - self.last_state_change,
            "half_open_attempts": self.half_open_attempts if self.state == CircuitState.HALF_OPEN else None
        }
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking calls)"""
        return self.state == CircuitState.OPEN and not self.call_allowed()

# Global circuit breaker instance
circuit_breaker = CircuitBreaker()