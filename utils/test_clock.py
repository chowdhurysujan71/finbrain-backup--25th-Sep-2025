"""
Test Clock Utility for Deterministic Testing

Provides X-Test-Now header support for non-production environments.
Allows tests to control time for reproducible banner and nudge testing.
"""

import os
from datetime import datetime, UTC
from typing import Optional
from flask import request
import logging

logger = logging.getLogger(__name__)

def is_testing_environment() -> bool:
    """Check if we're in a testing environment where test clock is allowed."""
    # Only allow test clock in non-production environments
    env = os.getenv('ENVIRONMENT', 'development').lower()
    return env in ('test', 'development', 'staging')

def get_current_time() -> datetime:
    """
    Get current time, with test override support in non-production environments.
    
    Returns:
        datetime: Current time or test time if X-Test-Now header is present
    """
    # Only allow test time override in testing environments
    if not is_testing_environment():
        return datetime.now(UTC)
    
    # Check for X-Test-Now header
    test_time_header = request.headers.get('X-Test-Now')
    
    if test_time_header:
        try:
            # Parse ISO format: 2025-09-28T10:30:00Z
            test_time = datetime.fromisoformat(test_time_header.replace('Z', '+00:00'))
            
            # Ensure timezone is UTC
            if test_time.tzinfo is None:
                test_time = test_time.replace(tzinfo=UTC)
            
            logger.debug(f"Using test time from X-Test-Now header: {test_time}")
            return test_time
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid X-Test-Now header format '{test_time_header}': {e}")
            # Fall back to real time
            return datetime.now(UTC)
    
    # No test time header, use real time
    return datetime.now(UTC)

def format_test_time(dt: datetime) -> str:
    """
    Format datetime for X-Test-Now header.
    
    Args:
        dt: datetime to format
        
    Returns:
        str: ISO formatted string for header
    """
    return dt.isoformat().replace('+00:00', 'Z')

class TestTimeContext:
    """Context manager for setting test time in testing environments."""
    
    def __init__(self, test_time: datetime):
        self.test_time = test_time
        self.original_headers = None
        
    def __enter__(self):
        if not is_testing_environment():
            logger.warning("TestTimeContext ignored in production environment")
            return self
            
        # This would require request context patching in actual tests
        # For now, just log the intended test time
        logger.info(f"Test time context: {format_test_time(self.test_time)}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not is_testing_environment():
            return
            
        logger.info("Test time context ended")

def get_banner_test_time() -> datetime:
    """
    Get current time for banner expiration checks with test override support.
    
    Returns:
        datetime: Current time or test time for banner logic
    """
    return get_current_time()

def get_spending_analysis_time() -> datetime:
    """
    Get current time for spending analysis with test override support.
    
    Returns:
        datetime: Current time or test time for spending calculations  
    """
    return get_current_time()

# Constants for testing
TEST_TIME_HEADER = 'X-Test-Now'
TEST_TIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

def create_test_headers(test_time: datetime) -> dict:
    """
    Create headers dict with test time for testing.
    
    Args:
        test_time: datetime to use for testing
        
    Returns:
        dict: Headers with X-Test-Now set
    """
    return {TEST_TIME_HEADER: format_test_time(test_time)}