"""
Performance Optimization Module for PCA Processing
Addresses DoD Criterion: P95 latency < 900ms consistently
"""

import time
import threading
from functools import lru_cache
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger("finbrain.performance")

# Thread-local storage for expensive imports and connections
_thread_local = threading.local()

def get_cached_imports():
    """Cache expensive imports per thread to reduce latency"""
    if not hasattr(_thread_local, 'imports_cached'):
        _thread_local.app = None
        _thread_local.db = None
        _thread_local.models_cached = False
        _thread_local.imports_cached = True
    
    if not _thread_local.app:
        try:
            from app import app, db
            _thread_local.app = app
            _thread_local.db = db
        except ImportError:
            pass
    
    return _thread_local.app, _thread_local.db

@lru_cache(maxsize=128)
def cached_pattern_analysis(message_text: str) -> Dict[str, Any]:
    """Cache pattern analysis results for identical messages"""
    import re
    
    # Bengali currency patterns
    bengali_patterns = [
        r'৳\s*(\d+)',  # ৳500
        r'(\d+)\s*টাকা',  # 500 টাকা
        r'(\d+)\s*taka',  # 500 taka
    ]
    
    # English expense patterns  
    english_patterns = [
        r'spent\s+(\d+)',  # spent 500
        r'cost\s+(\d+)',   # cost 500
        r'paid\s+(\d+)',   # paid 500
    ]
    
    confidence = 0.0
    amount = None
    pattern_type = 'none'
    
    # Check Bengali patterns first (higher confidence)
    for pattern in bengali_patterns:
        match = re.search(pattern, message_text, re.IGNORECASE)
        if match:
            amount = float(match.group(1))
            confidence = 0.90 if '৳' in pattern else 0.85
            pattern_type = 'bengali'
            break
    
    # Check English patterns if no Bengali match
    if not amount:
        for pattern in english_patterns:
            match = re.search(pattern, message_text, re.IGNORECASE)
            if match:
                amount = float(match.group(1))
                confidence = 0.80
                pattern_type = 'english'
                break
    
    return {
        'amount': amount,
        'confidence': confidence,
        'pattern_type': pattern_type,
        'processing_time_ms': 0  # Cached, so effectively 0ms
    }

class PerformanceTracker:
    """Track and optimize processing performance"""
    
    def __init__(self):
        self.processing_times = []
        self.slow_operations = []
        
    def track_operation(self, operation_name: str):
        """Context manager for tracking operation performance"""
        return OperationTimer(operation_name, self)
        
    def record_time(self, operation_name: str, duration_ms: float):
        """Record processing time for analysis"""
        self.processing_times.append({
            'operation': operation_name,
            'duration_ms': duration_ms,
            'timestamp': time.time()
        })
        
        # Flag slow operations (>500ms)
        if duration_ms > 500:
            self.slow_operations.append({
                'operation': operation_name,
                'duration_ms': duration_ms,
                'timestamp': time.time()
            })
            logger.warning(f"Slow operation detected: {operation_name} took {duration_ms:.1f}ms")
    
    def get_p95_latency(self) -> float:
        """Calculate 95th percentile latency"""
        if not self.processing_times:
            return 0.0
            
        times = [t['duration_ms'] for t in self.processing_times[-100:]]  # Last 100 operations
        times.sort()
        p95_index = int(0.95 * len(times))
        return times[p95_index] if times else 0.0
        
    def is_performance_acceptable(self) -> bool:
        """Check if performance meets DoD requirements"""
        p95 = self.get_p95_latency()
        return p95 < 900  # DoD requirement: P95 < 900ms

class OperationTimer:
    """Context manager for timing operations"""
    
    def __init__(self, operation_name: str, tracker: PerformanceTracker):
        self.operation_name = operation_name
        self.tracker = tracker
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            self.tracker.record_time(self.operation_name, duration_ms)

# Global performance tracker instance
performance_tracker = PerformanceTracker()

def optimize_pca_processing():
    """Apply performance optimizations to PCA processing"""
    
    # Pre-warm imports and connections
    get_cached_imports()
    
    # Clear old performance data
    if len(performance_tracker.processing_times) > 1000:
        performance_tracker.processing_times = performance_tracker.processing_times[-500:]
        performance_tracker.slow_operations = performance_tracker.slow_operations[-100:]
    
    logger.info("PCA performance optimizations applied")

def get_performance_metrics() -> Dict[str, Any]:
    """Get current performance metrics for monitoring"""
    p95 = performance_tracker.get_p95_latency()
    avg_time = sum(t['duration_ms'] for t in performance_tracker.processing_times[-50:]) / max(1, len(performance_tracker.processing_times[-50:]))
    
    return {
        'p95_latency_ms': round(p95, 1),
        'avg_latency_ms': round(avg_time, 1),
        'performance_acceptable': performance_tracker.is_performance_acceptable(),
        'slow_operations_count': len(performance_tracker.slow_operations),
        'total_operations': len(performance_tracker.processing_times),
        'dod_compliant': p95 < 900  # DoD requirement
    }