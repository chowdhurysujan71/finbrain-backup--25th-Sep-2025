"""
APScheduler integration for nightly data integrity checks
Manages scheduled execution of data integrity validation
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .data_integrity_check import IntegrityReport, run_integrity_check

logger = logging.getLogger(__name__)

class IntegrityScheduler:
    """Manages scheduled data integrity checks"""
    
    def __init__(self):
        self.scheduler = None
        self.last_report: IntegrityReport | None = None
        self.last_run_time: datetime | None = None
        self.is_running = False
        
        # Configure scheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(max_workers=1)  # Single threaded for DB integrity
        }
        job_defaults = {
            'coalesce': False,  # Don't merge missed jobs
            'max_instances': 1,  # Only one integrity check at a time
            'misfire_grace_time': 300  # 5 minutes grace for missed jobs
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
    def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Integrity scheduler already running")
            return
            
        try:
            # Schedule nightly check at 2 AM UTC
            self.scheduler.add_job(
                func=self._run_scheduled_check,
                trigger=CronTrigger(hour=2, minute=0),  # 2:00 AM UTC daily
                id='nightly_integrity_check',
                name='Nightly Data Integrity Check',
                replace_existing=True
            )
            
            # Also schedule a quick check every 6 hours during development
            if os.getenv('ENVIRONMENT') == 'development':
                self.scheduler.add_job(
                    func=self._run_scheduled_check,
                    trigger=CronTrigger(hour='*/6'),  # Every 6 hours
                    id='dev_integrity_check',
                    name='Development Integrity Check',
                    replace_existing=True
                )
            
            self.scheduler.start()
            self.is_running = True
            logger.info("Data integrity scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start integrity scheduler: {e}")
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler and self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("Data integrity scheduler stopped")
    
    def _run_scheduled_check(self):
        """Run the scheduled integrity check with error handling"""
        logger.info("Starting scheduled data integrity check")
        
        try:
            # Import here to avoid circular imports
            from app import app
            
            with app.app_context():
                report = run_integrity_check()
                self.last_report = report
                self.last_run_time = datetime.utcnow()
                
                # Log results
                logger.info(f"Integrity check completed: {report.overall_status}")
                logger.info(f"Summary: {report.summary}")
                
                # Send alerts if there are failures
                if report.overall_status in ['CRITICAL', 'WARNING']:
                    self._send_alert(report)
                
                # Store results for health endpoint
                self._store_results(report)
                
        except Exception as e:
            logger.error(f"Scheduled integrity check failed: {e}")
            # Create failure report
            self.last_report = self._create_failure_report(str(e))
            self.last_run_time = datetime.utcnow()
    
    def run_manual_check(self) -> IntegrityReport:
        """Run integrity check manually (for API endpoints)"""
        try:
            report = run_integrity_check()
            self.last_report = report
            self.last_run_time = datetime.utcnow()
            return report
        except Exception as e:
            logger.error(f"Manual integrity check failed: {e}")
            return self._create_failure_report(str(e))
    
    def get_status(self) -> dict[str, Any]:
        """Get current status of integrity checks"""
        next_run = None
        if self.scheduler and self.is_running:
            job = self.scheduler.get_job('nightly_integrity_check')
            if job:
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
        
        return {
            'scheduler_running': self.is_running,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
            'next_scheduled_run': next_run,
            'last_report_status': self.last_report.overall_status if self.last_report else None,
            'last_report_summary': self.last_report.summary if self.last_report else None,
            'checks_enabled': True
        }
    
    def get_last_report(self) -> IntegrityReport | None:
        """Get the last integrity check report"""
        return self.last_report
    
    def _send_alert(self, report: IntegrityReport):
        """Send alert for integrity check failures using integrated alerting system"""
        try:
            # Import and use the integrated alerting system
            from .integrity_alerts import integrity_alerting
            
            # Send alert via all configured channels
            integrity_alerting.send_alert(report)
            
            # Also log critical information locally
            failed_checks = [c for c in report.checks if c.status == 'FAIL']
            warning_checks = [c for c in report.checks if c.status == 'WARNING']
            
            alert_message = f"Data Integrity Alert - {report.overall_status}\n"
            alert_message += f"Run ID: {report.run_id}\n"
            alert_message += f"Summary: {report.summary}\n\n"
            
            if failed_checks:
                alert_message += "FAILED CHECKS:\n"
                for check in failed_checks:
                    alert_message += f"- {check.check_name}: {check.message}\n"
                    if check.affected_count > 0:
                        alert_message += f"  Affected count: {check.affected_count}\n"
            
            if warning_checks:
                alert_message += "\nWARNING CHECKS:\n"
                for check in warning_checks:
                    alert_message += f"- {check.check_name}: {check.message}\n"
                    if check.affected_count > 0:
                        alert_message += f"  Affected count: {check.affected_count}\n"
            
            # Log the alert for local audit trail
            logger.critical(f"INTEGRITY ALERT:\n{alert_message}")
            
        except Exception as e:
            logger.error(f"Failed to send integrity alert: {e}")
    
    def _store_results(self, report: IntegrityReport):
        """Store integrity check results for persistence (if needed)"""
        try:
            # In production, you might want to store results in database
            # or send to monitoring/observability system
            
            # For now, just ensure we have the results in memory
            # and log key metrics
            
            logger.info(f"Integrity check metrics: "
                       f"passed={report.passed}, "
                       f"failed={report.failed}, "
                       f"warnings={report.warnings}, "
                       f"total_checks={report.total_checks}")
            
            # TODO: Store in database table for historical tracking
            # TODO: Send metrics to monitoring system (Prometheus, DataDog, etc.)
            
        except Exception as e:
            logger.error(f"Failed to store integrity results: {e}")
    
    def _create_failure_report(self, error_message: str) -> IntegrityReport:
        """Create a failure report when the check itself fails"""
        from .data_integrity_check import IntegrityCheckResult
        
        failure_check = IntegrityCheckResult(
            check_name="Integrity Check System",
            status="FAIL",
            message=f"Integrity check system failed: {error_message}",
            affected_count=0
        )
        
        return IntegrityReport(
            run_id=f"failed_{int(datetime.utcnow().timestamp())}",
            start_time=datetime.utcnow().isoformat(),
            end_time=datetime.utcnow().isoformat(),
            total_checks=1,
            passed=0,
            failed=1,
            warnings=0,
            overall_status='CRITICAL',
            checks=[failure_check],
            summary=f"❌ SYSTEM FAILURE - Integrity check system failed: {error_message}"
        )

# Global instance
integrity_scheduler = IntegrityScheduler()