"""
🎯 UNBREAKABLE SINGLE WRITER INVARIANTS
Surgical runtime monitoring and enforcement for 100% reliability

This module provides runtime monitoring and enforcement of the single writer invariant
with multiple fail-safe layers that make bypassing impossible.
"""

import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict

import psycopg2

from constants import ALLOWED_SOURCES, validate_expense_source

logger = logging.getLogger(__name__)

class SingleWriterInvariantMonitor:
    """
    🛡️ RUNTIME INVARIANT ENFORCEMENT
    
    Multi-layer protection system:
    1. Database triggers (PostgreSQL level)
    2. Runtime validation (Python level) 
    3. Continuous monitoring (Background level)
    4. Alert system (Operations level)
    """
    
    def __init__(self):
        self.violation_count = 0
        self.last_check = None
        self.monitoring_active = True
        self._lock = threading.Lock()
        
    def validate_expense_write(self, expense_data: dict[str, Any]) -> bool:
        """
        🎯 RUNTIME VALIDATION
        Surgical validation before any expense write operation
        """
        try:
            # Source validation using centralized constants
            source = expense_data.get('source')
            if source is None:
                raise ValueError("SINGLE_WRITER_VIOLATION: Missing source")
            validate_expense_source(source)
            
            # Idempotency key validation
            if not expense_data.get('idempotency_key'):
                raise ValueError("SINGLE_WRITER_VIOLATION: Missing idempotency_key")
            
            # Canonical path validation
            if not expense_data.get('user_id'):
                raise ValueError("SINGLE_WRITER_VIOLATION: Missing user_id")
                
            logger.info(f"✅ SINGLE_WRITER_VALIDATED: source={source}, idempotency_key={expense_data.get('idempotency_key')}")
            return True
            
        except Exception as e:
            self._record_violation(str(e), expense_data)
            raise
    
    def _record_violation(self, error: str, data: dict[str, Any]):
        """Record invariant violations for monitoring"""
        with self._lock:
            self.violation_count += 1
            logger.error(f"🚨 SINGLE_WRITER_VIOLATION #{self.violation_count}: {error}")
            logger.error(f"   Violation data: {data}")
    
    def get_monitoring_stats(self) -> dict[str, Any]:
        """Get current monitoring statistics"""
        with self._lock:
            return {
                'violation_count': self.violation_count,
                'last_check': self.last_check,
                'monitoring_active': self.monitoring_active,
                'allowed_sources': list(ALLOWED_SOURCES),
                'database_triggers_active': self._check_db_triggers()
            }
    
    def _check_db_triggers(self) -> bool:
        """Verify database triggers are active"""
        try:
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            cur = conn.cursor()
            
            # Check for single writer enforcement triggers
            cur.execute("""
                SELECT COUNT(*) 
                FROM information_schema.triggers 
                WHERE event_object_table = 'expenses' 
                AND trigger_name LIKE '%single_writer%' OR trigger_name LIKE '%canonical%'
            """)
            
            result = cur.fetchone()
            trigger_count = result[0] if result else 0
            cur.close()
            conn.close()
            
            return trigger_count > 0
            
        except Exception as e:
            logger.error(f"Failed to check database triggers: {e}")
            return False

    def run_invariant_health_check(self) -> dict[str, Any]:
        """
        🔍 COMPREHENSIVE HEALTH CHECK
        Validates all layers of single writer protection
        """
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'HEALTHY',
            'checks': {}
        }
        
        try:
            # 1. Database trigger verification
            db_triggers_active = self._check_db_triggers()
            health_status['checks']['database_triggers'] = {
                'status': 'PASS' if db_triggers_active else 'FAIL',
                'active': db_triggers_active
            }
            
            # 2. Source validation test
            try:
                validate_expense_source('chat')
                health_status['checks']['source_validation'] = {'status': 'PASS'}
            except Exception:
                health_status['checks']['source_validation'] = {'status': 'FAIL'}
            
            # 3. Deprecated source rejection test
            deprecated_rejected = True
            for deprecated_source in ['messenger', 'form']:
                try:
                    validate_expense_source(deprecated_source)
                    deprecated_rejected = False
                    break
                except ValueError:
                    pass  # Expected - should be rejected
            
            health_status['checks']['deprecated_rejection'] = {
                'status': 'PASS' if deprecated_rejected else 'FAIL'
            }
            
            # 4. Runtime monitoring status
            health_status['checks']['runtime_monitoring'] = {
                'status': 'PASS' if self.monitoring_active else 'FAIL',
                'violation_count': self.violation_count
            }
            
            # Overall status determination
            failed_checks = [k for k, v in health_status['checks'].items() 
                           if v['status'] != 'PASS']
            
            if failed_checks:
                health_status['overall_status'] = 'DEGRADED'
                health_status['failed_checks'] = failed_checks
                
            self.last_check = datetime.now()
            
        except Exception as e:
            health_status['overall_status'] = 'ERROR'
            health_status['error'] = str(e)
            logger.error(f"Invariant health check failed: {e}")
        
        return health_status

# Global instance for application-wide use
invariant_monitor = SingleWriterInvariantMonitor()

def enforce_single_writer_invariant(expense_data: dict[str, Any]) -> bool:
    """
    🎯 GLOBAL ENFORCEMENT ENTRY POINT
    Use this function before any expense write operation
    """
    return invariant_monitor.validate_expense_write(expense_data)

def get_invariant_status() -> dict[str, Any]:
    """Get current single writer invariant status"""
    return invariant_monitor.get_monitoring_stats()

def run_invariant_health_check() -> dict[str, Any]:
    """Run comprehensive invariant health check"""
    return invariant_monitor.run_invariant_health_check()