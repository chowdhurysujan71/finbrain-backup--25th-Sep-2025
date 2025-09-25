"""
📊 SLO MONITORING: MEASURABLE RELIABILITY TARGETS
Service Level Objectives monitoring for expense save operations and system reliability

This module implements comprehensive SLO tracking with:
- Expense save success rate monitoring (Target: 99.9%)
- Response time SLAs (Target: <500ms P95)
- Single writer enforcement SLOs (Target: 100% compliance)
- System availability monitoring (Target: 99.95% uptime)
"""

import logging
import threading
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class SLOStatusLevel(Enum):
    MEETING = "MEETING"
    AT_RISK = "AT_RISK" 
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"

class SLOMetricType(Enum):
    SUCCESS_RATE = "success_rate"
    RESPONSE_TIME = "response_time"
    AVAILABILITY = "availability"
    ERROR_RATE = "error_rate"

@dataclass
class SLOTarget:
    name: str
    metric_type: SLOMetricType
    target_value: float
    window_minutes: int
    description: str
    critical: bool = True

@dataclass
class SLOMeasurement:
    timestamp: datetime
    metric_type: SLOMetricType
    value: float
    success: bool
    response_time_ms: float | None = None
    error_message: str | None = None
    operation: str = "unknown"

@dataclass
class SLOStatusReport:
    target: SLOTarget
    current_value: float
    status: SLOStatusLevel
    measurements_count: int
    error_budget_remaining: float
    last_violation: datetime | None = None
    trend: str = "stable"  # improving, degrading, stable

class SLOMonitor:
    """
    📊 COMPREHENSIVE SLO MONITORING SYSTEM
    
    Tracks critical system SLOs:
    1. Expense Save Success Rate: 99.9% (critical)
    2. Response Time P95: <500ms (critical)
    3. Single Writer Compliance: 100% (critical)
    4. System Availability: 99.95% (critical)
    5. Error Rate: <0.1% (warning)
    """
    
    def __init__(self):
        self.measurements = defaultdict(deque)  # metric_type -> deque of measurements
        self.lock = threading.Lock()
        
        # Define SLO targets
        self.slo_targets = {
            'expense_save_success': SLOTarget(
                name="Expense Save Success Rate",
                metric_type=SLOMetricType.SUCCESS_RATE,
                target_value=99.9,  # 99.9% success rate
                window_minutes=60,  # 1 hour window
                description="Percentage of successful expense save operations",
                critical=True
            ),
            'response_time_p95': SLOTarget(
                name="Response Time P95",
                metric_type=SLOMetricType.RESPONSE_TIME,
                target_value=500.0,  # 500ms P95
                window_minutes=15,  # 15 minute window
                description="95th percentile response time for expense operations",
                critical=True
            ),
            'single_writer_compliance': SLOTarget(
                name="Single Writer Compliance",
                metric_type=SLOMetricType.SUCCESS_RATE,
                target_value=100.0,  # 100% compliance
                window_minutes=60,  # 1 hour window
                description="Percentage of expense operations using canonical writer",
                critical=True
            ),
            'system_availability': SLOTarget(
                name="System Availability",
                metric_type=SLOMetricType.AVAILABILITY,
                target_value=99.95,  # 99.95% uptime
                window_minutes=1440,  # 24 hour window
                description="System uptime and accessibility",
                critical=True
            ),
            'error_rate': SLOTarget(
                name="Error Rate",
                metric_type=SLOMetricType.ERROR_RATE,
                target_value=0.1,  # <0.1% error rate
                window_minutes=60,  # 1 hour window
                description="Percentage of requests resulting in errors",
                critical=False
            )
        }
        
        # Initialize measurement storage
        for target_name in self.slo_targets.keys():
            self.measurements[target_name] = deque(maxlen=10000)  # Keep last 10k measurements
    
    def record_expense_save_attempt(self, success: bool, response_time_ms: float, 
                                  operation: str = "expense_save", 
                                  error_message: str | None = None,
                                  single_writer_compliant: bool = True) -> None:
        """
        📝 RECORD EXPENSE SAVE ATTEMPT
        Record a single expense save operation for SLO tracking
        """
        timestamp = datetime.now()
        
        with self.lock:
            # Record expense save success rate
            self.measurements['expense_save_success'].append(SLOMeasurement(
                timestamp=timestamp,
                metric_type=SLOMetricType.SUCCESS_RATE,
                value=100.0 if success else 0.0,
                success=success,
                response_time_ms=response_time_ms,
                error_message=error_message,
                operation=operation
            ))
            
            # Record response time
            self.measurements['response_time_p95'].append(SLOMeasurement(
                timestamp=timestamp,
                metric_type=SLOMetricType.RESPONSE_TIME,
                value=response_time_ms,
                success=response_time_ms < 500.0,  # Success if under 500ms
                response_time_ms=response_time_ms,
                operation=operation
            ))
            
            # Record single writer compliance
            self.measurements['single_writer_compliance'].append(SLOMeasurement(
                timestamp=timestamp,
                metric_type=SLOMetricType.SUCCESS_RATE,
                value=100.0 if single_writer_compliant else 0.0,
                success=single_writer_compliant,
                response_time_ms=response_time_ms,
                operation=operation
            ))
            
            # Record error rate (inverse of success)
            self.measurements['error_rate'].append(SLOMeasurement(
                timestamp=timestamp,
                metric_type=SLOMetricType.ERROR_RATE,
                value=0.0 if success else 100.0,
                success=success,
                response_time_ms=response_time_ms,
                error_message=error_message,
                operation=operation
            ))
    
    def record_system_health_check(self, healthy: bool, response_time_ms: float) -> None:
        """
        🏥 RECORD SYSTEM HEALTH CHECK
        Record system availability measurement
        """
        timestamp = datetime.now()
        
        with self.lock:
            self.measurements['system_availability'].append(SLOMeasurement(
                timestamp=timestamp,
                metric_type=SLOMetricType.AVAILABILITY,
                value=100.0 if healthy else 0.0,
                success=healthy,
                response_time_ms=response_time_ms,
                operation="health_check"
            ))
    
    def get_current_slo_status(self) -> dict[str, Any]:
        """
        📊 GET CURRENT SLO STATUS
        Calculate current SLO status for all targets
        """
        slo_status = {}
        
        with self.lock:
            for target_name, target in self.slo_targets.items():
                status = self._calculate_slo_status(target_name, target)
                slo_status[target_name] = asdict(status) if status else None
        
        # Calculate overall system health
        critical_slos = [status for status in slo_status.values() if status and status['target']['critical']]
        violated_critical = [slo for slo in critical_slos if slo['status'] == SLOStatusLevel.VIOLATED.value]
        at_risk_critical = [slo for slo in critical_slos if slo['status'] == SLOStatusLevel.AT_RISK.value]
        
        overall_health = "HEALTHY"
        if violated_critical:
            overall_health = "CRITICAL"
        elif at_risk_critical:
            overall_health = "DEGRADED"
        elif len([slo for slo in slo_status.values() if slo and slo['status'] == SLOStatusLevel.VIOLATED.value]) > 0:
            overall_health = "NEEDS_ATTENTION"
        
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_health': overall_health,
            'slo_statuses': slo_status,
            'summary': {
                'total_slos': len(self.slo_targets),
                'meeting_slos': len([s for s in slo_status.values() if s and s['status'] == SLOStatusLevel.MEETING.value]),
                'at_risk_slos': len([s for s in slo_status.values() if s and s['status'] == SLOStatusLevel.AT_RISK.value]),
                'violated_slos': len([s for s in slo_status.values() if s and s['status'] == SLOStatusLevel.VIOLATED.value]),
                'critical_violated': len(violated_critical)
            }
        }
    
    def _calculate_slo_status(self, target_name: str, target: SLOTarget) -> SLOStatusReport | None:
        """Calculate SLO status for a specific target"""
        measurements = self.measurements[target_name]
        if not measurements:
            return None
        
        # Filter measurements within the time window
        cutoff_time = datetime.now() - timedelta(minutes=target.window_minutes)
        recent_measurements = [m for m in measurements if m.timestamp >= cutoff_time]
        
        if not recent_measurements:
            return SLOStatusReport(
                target=target,
                current_value=0.0,
                status=SLOStatusLevel.UNKNOWN,
                measurements_count=0,
                error_budget_remaining=100.0
            )
        
        # Calculate current value based on metric type
        if target.metric_type in [SLOMetricType.SUCCESS_RATE, SLOMetricType.AVAILABILITY]:
            # Average of success percentage
            current_value = sum(m.value for m in recent_measurements) / len(recent_measurements)
        elif target.metric_type == SLOMetricType.RESPONSE_TIME:
            # P95 calculation
            values = sorted([m.value for m in recent_measurements])
            p95_index = int(0.95 * len(values))
            current_value = values[p95_index] if p95_index < len(values) else values[-1]
        elif target.metric_type == SLOMetricType.ERROR_RATE:
            # Average error rate
            current_value = sum(m.value for m in recent_measurements) / len(recent_measurements)
        else:
            current_value = 0.0
        
        # Determine status
        if target.metric_type == SLOMetricType.RESPONSE_TIME:
            # For response time, lower is better
            if current_value <= target.target_value:
                status = SLOStatusLevel.MEETING
            elif current_value <= target.target_value * 1.2:  # 20% margin
                status = SLOStatusLevel.AT_RISK
            else:
                status = SLOStatusLevel.VIOLATED
        elif target.metric_type == SLOMetricType.ERROR_RATE:
            # For error rate, lower is better
            if current_value <= target.target_value:
                status = SLOStatusLevel.MEETING
            elif current_value <= target.target_value * 2:  # 100% margin
                status = SLOStatusLevel.AT_RISK
            else:
                status = SLOStatusLevel.VIOLATED
        else:
            # For success rate and availability, higher is better
            if current_value >= target.target_value:
                status = SLOStatusLevel.MEETING
            elif current_value >= target.target_value * 0.95:  # 5% margin
                status = SLOStatusLevel.AT_RISK
            else:
                status = SLOStatusLevel.VIOLATED
        
        # Calculate error budget remaining
        if target.metric_type == SLOMetricType.RESPONSE_TIME:
            error_budget_remaining = max(0, (target.target_value - current_value) / target.target_value * 100)
        elif target.metric_type == SLOMetricType.ERROR_RATE:
            error_budget_remaining = max(0, (target.target_value - current_value) / target.target_value * 100)
        else:
            error_budget_remaining = max(0, current_value - target.target_value)
        
        # Find last violation
        last_violation = None
        for measurement in reversed(recent_measurements):
            if target.metric_type == SLOMetricType.RESPONSE_TIME:
                if measurement.value > target.target_value:
                    last_violation = measurement.timestamp
                    break
            elif target.metric_type == SLOMetricType.ERROR_RATE:
                if measurement.value > target.target_value:
                    last_violation = measurement.timestamp
                    break
            else:
                if measurement.value < target.target_value:
                    last_violation = measurement.timestamp
                    break
        
        return SLOStatusReport(
            target=target,
            current_value=current_value,
            status=status,
            measurements_count=len(recent_measurements),
            error_budget_remaining=error_budget_remaining,
            last_violation=last_violation
        )
    
    def get_slo_trends(self, hours: int = 24) -> dict[str, Any]:
        """
        📈 GET SLO TRENDS
        Analyze SLO trends over specified time period
        """
        trends = {}
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self.lock:
            for target_name, target in self.slo_targets.items():
                measurements = [m for m in self.measurements[target_name] if m.timestamp >= cutoff_time]
                
                if len(measurements) < 2:
                    continue
                
                # Split into time buckets for trend analysis
                bucket_size = timedelta(hours=1)  # 1-hour buckets
                buckets = defaultdict(list)
                
                for measurement in measurements:
                    bucket_key = measurement.timestamp.replace(minute=0, second=0, microsecond=0)
                    buckets[bucket_key].append(measurement)
                
                # Calculate trend
                bucket_values = []
                for bucket_time in sorted(buckets.keys()):
                    bucket_measurements = buckets[bucket_time]
                    if target.metric_type == SLOMetricType.RESPONSE_TIME:
                        # P95 for each bucket
                        values = sorted([m.value for m in bucket_measurements])
                        p95_index = int(0.95 * len(values))
                        bucket_value = values[p95_index] if p95_index < len(values) else values[-1]
                    else:
                        # Average for each bucket
                        bucket_value = sum(m.value for m in bucket_measurements) / len(bucket_measurements)
                    
                    bucket_values.append(bucket_value)
                
                # Determine trend direction
                if len(bucket_values) >= 3:
                    recent_avg = sum(bucket_values[-3:]) / 3
                    earlier_avg = sum(bucket_values[:3]) / 3
                    
                    if target.metric_type in [SLOMetricType.SUCCESS_RATE, SLOMetricType.AVAILABILITY]:
                        # Higher is better
                        if recent_avg > earlier_avg * 1.02:
                            trend_direction = "improving"
                        elif recent_avg < earlier_avg * 0.98:
                            trend_direction = "degrading"
                        else:
                            trend_direction = "stable"
                    else:
                        # Lower is better (response time, error rate)
                        if recent_avg < earlier_avg * 0.98:
                            trend_direction = "improving"
                        elif recent_avg > earlier_avg * 1.02:
                            trend_direction = "degrading"
                        else:
                            trend_direction = "stable"
                else:
                    trend_direction = "stable"
                
                trends[target_name] = {
                    'trend_direction': trend_direction,
                    'data_points': len(bucket_values),
                    'time_period_hours': hours,
                    'current_value': bucket_values[-1] if bucket_values else 0,
                    'historical_values': bucket_values[-24:]  # Last 24 hours
                }
        
        return trends
    
    def get_slo_violations_summary(self, hours: int = 24) -> dict[str, Any]:
        """
        🚨 GET SLO VIOLATIONS SUMMARY
        Summary of SLO violations in the specified time period
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        violations = []
        
        with self.lock:
            for target_name, target in self.slo_targets.items():
                measurements = [m for m in self.measurements[target_name] if m.timestamp >= cutoff_time]
                
                for measurement in measurements:
                    is_violation = False
                    
                    if target.metric_type == SLOMetricType.RESPONSE_TIME:
                        is_violation = measurement.value > target.target_value
                    elif target.metric_type == SLOMetricType.ERROR_RATE:
                        is_violation = measurement.value > target.target_value
                    else:
                        is_violation = measurement.value < target.target_value
                    
                    if is_violation:
                        violations.append({
                            'target_name': target_name,
                            'target_description': target.description,
                            'timestamp': measurement.timestamp.isoformat(),
                            'value': measurement.value,
                            'target_value': target.target_value,
                            'operation': measurement.operation,
                            'error_message': measurement.error_message,
                            'critical': target.critical
                        })
        
        # Group violations by target
        violations_by_target = defaultdict(list)
        for violation in violations:
            violations_by_target[violation['target_name']].append(violation)
        
        return {
            'time_period_hours': hours,
            'total_violations': len(violations),
            'critical_violations': len([v for v in violations if v['critical']]),
            'violations_by_target': dict(violations_by_target),
            'most_recent_violation': violations[-1] if violations else None
        }

# Global SLO monitor instance
slo_monitor = SLOMonitor()

def record_expense_operation(success: bool, response_time_ms: float, 
                           operation: str = "expense_save",
                           single_writer_compliant: bool = True,
                           error_message: str | None = None) -> None:
    """
    📊 GLOBAL ENTRY POINT
    Record an expense operation for SLO tracking
    """
    slo_monitor.record_expense_save_attempt(
        success=success,
        response_time_ms=response_time_ms,
        operation=operation,
        error_message=error_message,
        single_writer_compliant=single_writer_compliant
    )

def get_slo_dashboard() -> dict[str, Any]:
    """
    📊 GET SLO DASHBOARD
    Get comprehensive SLO dashboard data
    """
    current_status = slo_monitor.get_current_slo_status()
    trends = slo_monitor.get_slo_trends(hours=24)
    violations = slo_monitor.get_slo_violations_summary(hours=24)
    
    return {
        'current_status': current_status,
        'trends': trends,
        'violations': violations,
        'dashboard_generated': datetime.now().isoformat()
    }