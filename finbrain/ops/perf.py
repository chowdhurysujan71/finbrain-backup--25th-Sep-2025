"""
Performance monitoring with ring buffer and P95 calculation
"""

import time
from typing import Optional, List

class LatencyMonitor:
    """Ring buffer for tracking request latencies with P95 calculation"""
    
    def __init__(self, size: int = 500):
        self.size = size
        self.buffer: List[float] = []
        self.index = 0
        self.full = False
    
    def record(self, latency: float) -> None:
        """Record a latency measurement"""
        if len(self.buffer) < self.size:
            self.buffer.append(latency)
        else:
            self.buffer[self.index] = latency
            self.full = True
        
        self.index = (self.index + 1) % self.size
    
    def count(self) -> int:
        """Get number of recorded samples"""
        return len(self.buffer)
    
    def p95(self) -> Optional[float]:
        """Calculate P95 using nearest rank method"""
        if not self.buffer:
            return None
        
        sorted_values = sorted(self.buffer)
        n = len(sorted_values)
        
        # P95 using nearest rank method
        rank = int(0.95 * n)
        if rank >= n:
            rank = n - 1
        
        return sorted_values[rank]
    
    def clear(self) -> None:
        """Clear all recorded data for testing"""
        self.buffer.clear()
        self.index = 0
        self.full = False


# Global instance
_monitor = LatencyMonitor()

def record(latency: float) -> None:
    """Record a latency measurement"""
    _monitor.record(latency)

def count() -> int:
    """Get number of recorded samples"""
    return _monitor.count()

def p95() -> Optional[float]:
    """Get P95 latency"""
    return _monitor.p95()

def clear() -> None:
    """Clear all recorded data for testing"""
    _monitor.clear()