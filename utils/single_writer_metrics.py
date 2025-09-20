"""
Single Writer Metrics & Observability

Provides monitoring, alerting, and SLA tracking for the single writer principle enforcement.
This module ensures we can detect violations, performance issues, and system health.
"""

import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class ViolationType(Enum):
    """Types of single writer violations"""
    UNAUTHORIZED_WRITE = "unauthorized_write"
    BYPASS_ATTEMPT = "bypass_attempt"
    GHOST_CODE_REINTRODUCTION = "ghost_code_reintroduction"
    DIRECT_MODEL_ACCESS = "direct_model_access"
    CI_CHECK_FAILURE = "ci_check_failure"

@dataclass
class SingleWriterMetric:
    """Single metric data point"""
    timestamp: float
    metric_type: str
    value: float
    tags: Dict[str, str]
    source: str

@dataclass
class ViolationEvent:
    """Single writer violation event"""
    timestamp: float
    violation_type: ViolationType
    source: str
    details: Dict[str, Any]
    severity: str  # "low", "medium", "high", "critical"
    resolved: bool = False

class SingleWriterMonitor:
    """
    Comprehensive monitoring system for single writer principle enforcement.
    
    Tracks:
    - Canonical writer usage
    - Runtime protection triggers
    - CI check results
    - System performance metrics
    - Violation events and alerts
    """
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=10000)  # Last 10k metrics
        self._violations: List[ViolationEvent] = []
        self._hourly_stats = defaultdict(int)
        self._daily_stats = defaultdict(int)
        self._lock = threading.Lock()
        
        # SLA targets
        self.sla_targets = {
            'canonical_writer_success_rate': 99.9,  # 99.9% success rate
            'runtime_protection_response_time': 100,  # < 100ms response time
            'violation_detection_time': 60,  # < 60s to detect violations
            'zero_unauthorized_writes': True,  # Zero tolerance for unauthorized writes
        }
        
        logger.info("Single Writer Monitor initialized with SLA targets")
    
    def record_canonical_write(self, user_id: str, success: bool, duration_ms: float, **kwargs):
        """Record a canonical writer operation"""
        with self._lock:
            metric = SingleWriterMetric(
                timestamp=time.time(),
                metric_type="canonical_write",
                value=1 if success else 0,
                tags={
                    "success": str(success),
                    "user_id_prefix": user_id[:8] if user_id else "unknown",
                    "duration_bucket": self._get_duration_bucket(duration_ms),
                    **kwargs
                },
                source="backend_assistant"
            )
            self._metrics.append(metric)
            
            # Update stats
            hour_key = datetime.now().strftime("%Y-%m-%d_%H")
            day_key = datetime.now().strftime("%Y-%m-%d")
            
            if success:
                self._hourly_stats[f"{hour_key}_canonical_writes_success"] += 1
                self._daily_stats[f"{day_key}_canonical_writes_success"] += 1
            else:
                self._hourly_stats[f"{hour_key}_canonical_writes_failure"] += 1
                self._daily_stats[f"{day_key}_canonical_writes_failure"] += 1
                
            self._hourly_stats[f"{hour_key}_response_time_total"] += duration_ms
            self._daily_stats[f"{day_key}_response_time_total"] += duration_ms
    
    def record_protection_trigger(self, protection_type: str, blocked: bool, source: str, **kwargs):
        """Record a runtime protection trigger"""
        with self._lock:
            metric = SingleWriterMetric(
                timestamp=time.time(),
                metric_type="protection_trigger",
                value=1 if blocked else 0,
                tags={
                    "protection_type": protection_type,
                    "blocked": str(blocked),
                    "source": source,
                    **kwargs
                },
                source="runtime_guard"
            )
            self._metrics.append(metric)
            
            if blocked:
                # This is a successful block of unauthorized access
                hour_key = datetime.now().strftime("%Y-%m-%d_%H")
                day_key = datetime.now().strftime("%Y-%m-%d")
                self._hourly_stats[f"{hour_key}_blocks_successful"] += 1
                self._daily_stats[f"{day_key}_blocks_successful"] += 1
    
    def record_violation(self, violation_type: ViolationType, source: str, details: Dict[str, Any], severity: str = "medium"):
        """Record a single writer violation"""
        with self._lock:
            violation = ViolationEvent(
                timestamp=time.time(),
                violation_type=violation_type,
                source=source,
                details=details,
                severity=severity
            )
            self._violations.append(violation)
            
            # Log based on severity
            violation_msg = f"Single Writer Violation: {violation_type.value} from {source}"
            if severity == "critical":
                logger.error(f"🚨 CRITICAL {violation_msg}: {details}")
            elif severity == "high":
                logger.warning(f"⚠️  HIGH {violation_msg}: {details}")
            else:
                logger.info(f"ℹ️  {violation_msg}: {details}")
            
            # Update stats
            hour_key = datetime.now().strftime("%Y-%m-%d_%H")
            day_key = datetime.now().strftime("%Y-%m-%d")
            self._hourly_stats[f"{hour_key}_violations_{violation_type.value}"] += 1
            self._daily_stats[f"{day_key}_violations_{violation_type.value}"] += 1
    
    def record_ci_check_result(self, success: bool, violations_found: int, duration_ms: float):
        """Record CI check results"""
        with self._lock:
            metric = SingleWriterMetric(
                timestamp=time.time(),
                metric_type="ci_check",
                value=violations_found,
                tags={
                    "success": str(success),
                    "violations_found": str(violations_found),
                    "duration_bucket": self._get_duration_bucket(duration_ms)
                },
                source="ci_system"
            )
            self._metrics.append(metric)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status of single writer enforcement"""
        with self._lock:
            now = time.time()
            last_24h = now - (24 * 60 * 60)
            last_1h = now - (60 * 60)
            
            # Recent metrics
            recent_metrics = [m for m in self._metrics if m.timestamp >= last_24h]
            recent_violations = [v for v in self._violations if v.timestamp >= last_24h and not v.resolved]
            
            # Calculate success rates
            canonical_writes = [m for m in recent_metrics if m.metric_type == "canonical_write"]
            successful_writes = [m for m in canonical_writes if m.tags.get("success") == "True"]
            success_rate = (len(successful_writes) / len(canonical_writes) * 100) if canonical_writes else 100
            
            # Calculate response times
            response_times = [float(m.tags.get("duration_ms", 0)) for m in canonical_writes if "duration_ms" in m.tags]
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            p95_response_time = sorted(response_times)[int(0.95 * len(response_times))] if response_times else 0
            
            # Protection effectiveness
            protection_triggers = [m for m in recent_metrics if m.metric_type == "protection_trigger"]
            blocked_attempts = [m for m in protection_triggers if m.tags.get("blocked") == "True"]
            
            # SLA compliance
            sla_compliance = {
                "canonical_writer_success_rate": success_rate >= self.sla_targets["canonical_writer_success_rate"],
                "runtime_protection_response_time": avg_response_time <= self.sla_targets["runtime_protection_response_time"],
                "zero_unauthorized_writes": len([v for v in recent_violations if v.violation_type == ViolationType.UNAUTHORIZED_WRITE]) == 0
            }
            
            return {
                "status": "healthy" if all(sla_compliance.values()) and len(recent_violations) == 0 else "degraded",
                "timestamp": now,
                "metrics_24h": {
                    "canonical_writes_total": len(canonical_writes),
                    "canonical_writes_success_rate": round(success_rate, 2),
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "p95_response_time_ms": round(p95_response_time, 2),
                    "protection_triggers": len(protection_triggers),
                    "blocked_attempts": len(blocked_attempts),
                    "violations": len(recent_violations)
                },
                "sla_compliance": sla_compliance,
                "recent_violations": [asdict(v) for v in recent_violations[-5:]],  # Last 5 violations
                "protection_status": {
                    "runtime_guard": "active",
                    "ci_checks": "active", 
                    "database_constraints": "active"
                }
            }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard"""
        health = self.get_health_status()
        
        with self._lock:
            now = time.time()
            last_24h = now - (24 * 60 * 60)
            
            # Time series data for charts
            hourly_buckets = defaultdict(lambda: {"writes": 0, "violations": 0, "avg_response": 0})
            
            for metric in self._metrics:
                if metric.timestamp >= last_24h:
                    hour = datetime.fromtimestamp(metric.timestamp).strftime("%Y-%m-%d_%H")
                    
                    if metric.metric_type == "canonical_write" and metric.tags.get("success") == "True":
                        hourly_buckets[hour]["writes"] += 1
                        
            for violation in self._violations:
                if violation.timestamp >= last_24h:
                    hour = datetime.fromtimestamp(violation.timestamp).strftime("%Y-%m-%d_%H")
                    hourly_buckets[hour]["violations"] += 1
            
            return {
                "health": health,
                "time_series": dict(hourly_buckets),
                "sla_targets": self.sla_targets,
                "protection_layers": {
                    "database_constraints": {"status": "active", "description": "PostgreSQL constraints and triggers"},
                    "runtime_guards": {"status": "active", "description": "SQLAlchemy event listeners"},
                    "ci_checks": {"status": "active", "description": "Static analysis pre-commit"},
                    "canonical_writer": {"status": "active", "description": "backend_assistant.add_expense() enforcement"}
                }
            }
    
    def _get_duration_bucket(self, duration_ms: float) -> str:
        """Bucket duration for metrics"""
        if duration_ms < 10:
            return "0-10ms"
        elif duration_ms < 50:
            return "10-50ms"
        elif duration_ms < 100:
            return "50-100ms"
        elif duration_ms < 500:
            return "100-500ms"
        else:
            return "500ms+"

# Global monitor instance
single_writer_monitor = SingleWriterMonitor()

def record_canonical_write(user_id: str, success: bool, duration_ms: float, **kwargs):
    """Helper function to record canonical writer operations"""
    single_writer_monitor.record_canonical_write(user_id, success, duration_ms, **kwargs)

def record_violation(violation_type: ViolationType, source: str, details: Dict[str, Any], severity: str = "medium"):
    """Helper function to record violations"""
    single_writer_monitor.record_violation(violation_type, source, details, severity)

def record_protection_trigger(protection_type: str, blocked: bool, source: str, **kwargs):
    """Helper function to record protection triggers"""
    single_writer_monitor.record_protection_trigger(protection_type, blocked, source, **kwargs)

def get_health_status() -> Dict[str, Any]:
    """Helper function to get health status"""
    return single_writer_monitor.get_health_status()

def get_dashboard_data() -> Dict[str, Any]:
    """Helper function to get dashboard data"""
    return single_writer_monitor.get_dashboard_data()