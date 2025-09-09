"""
Timeout wrapper utility to prevent hanging AI calls
Provides guaranteed timeouts with fallback responses
"""
import time
import signal
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as Tmo
from typing import Callable, Any

logger = logging.getLogger(__name__)

# Thread pool for timeout operations
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="timebox")

def call_with_timeout(fn: Callable, timeout_s: float, *args, **kwargs) -> Any:
    """
    Execute function with guaranteed timeout
    
    Args:
        fn: Function to execute
        timeout_s: Maximum execution time in seconds
        *args, **kwargs: Arguments for the function
        
    Returns:
        Function result or raises TimeoutError
        
    Raises:
        TimeoutError: If function exceeds timeout
        Exception: Any exception from the underlying function
    """
    t0 = time.time()
    
    try:
        future = _pool.submit(fn, *args, **kwargs)
        result = future.result(timeout=timeout_s)
        elapsed = time.time() - t0
        logger.debug(f"Function {fn.__name__} completed in {elapsed:.2f}s")
        return result
        
    except Tmo:
        elapsed = time.time() - t0
        logger.warning(f"Function {fn.__name__} timed out after {elapsed:.2f}s (limit: {timeout_s}s)")
        # Try to cancel the future to free resources
        future.cancel()
        raise TimeoutError(f"Operation timed out after {timeout_s}s")
        
    except Exception as e:
        elapsed = time.time() - t0
        logger.warning(f"Function {fn.__name__} failed after {elapsed:.2f}s: {e}")
        raise

def call_with_timeout_fallback(fn: Callable, timeout_s: float, fallback_value: Any, *args, **kwargs) -> Any:
    """
    Execute function with timeout and return fallback on timeout/error
    
    Args:
        fn: Function to execute
        timeout_s: Maximum execution time in seconds  
        fallback_value: Value to return on timeout or error
        *args, **kwargs: Arguments for the function
        
    Returns:
        Function result or fallback_value
    """
    try:
        return call_with_timeout(fn, timeout_s, *args, **kwargs)
    except (TimeoutError, Exception) as e:
        logger.info(f"Using fallback for {fn.__name__}: {e}")
        return fallback_value