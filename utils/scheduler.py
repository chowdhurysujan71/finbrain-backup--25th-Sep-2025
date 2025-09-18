"""Task scheduling for automated reports and security cleanup"""
import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from utils.report_generator import send_daily_reports, send_weekly_reports
from utils.pending_expenses_cleanup import run_pending_expenses_cleanup

logger = logging.getLogger(__name__)

scheduler = None

def init_scheduler():
    """Initialize the background scheduler for automated reports"""
    global scheduler
    
    try:
        if scheduler is not None:
            return scheduler
        
        scheduler = BackgroundScheduler()
        
        # Daily reports at 8 PM local time
        scheduler.add_job(
            func=send_daily_reports,
            trigger=CronTrigger(hour=20, minute=0),
            id='daily_reports',
            name='Send daily expense reports',
            replace_existing=True
        )
        
        # Weekly reports on Sunday at 9 AM
        scheduler.add_job(
            func=send_weekly_reports,
            trigger=CronTrigger(day_of_week=0, hour=9, minute=0),
            id='weekly_reports',
            name='Send weekly expense reports',
            replace_existing=True
        )
        
        # Pending expenses cleanup every 7 minutes (security requirement)
        scheduler.add_job(
            func=run_pending_expenses_cleanup,
            trigger=IntervalTrigger(minutes=7),
            id='pending_expenses_cleanup',
            name='Clean up expired pending expenses',
            replace_existing=True,
            max_instances=1  # Prevent overlapping cleanup jobs
        )
        
        # Start the scheduler
        scheduler.start()
        logger.info("Scheduler initialized successfully with security cleanup jobs")
        
        return scheduler
        
    except Exception as e:
        logger.error(f"Error initializing scheduler: {str(e)}")
        return None

def stop_scheduler():
    """Stop the background scheduler"""
    global scheduler
    
    try:
        if scheduler and scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped successfully")
        
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")

def get_scheduler_status():
    """Get current scheduler status"""
    global scheduler
    
    try:
        if scheduler is None:
            return {'status': 'not_initialized', 'jobs': []}
        
        if not scheduler.running:
            return {'status': 'stopped', 'jobs': []}
        
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None
            })
        
        return {
            'status': 'running',
            'jobs': jobs
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        return {'status': 'error', 'jobs': []}

def trigger_daily_report_now():
    """Manually trigger daily report generation"""
    try:
        logger.info("Manually triggering daily reports")
        result = send_daily_reports()
        return {'success': True, 'reports_sent': result}
        
    except Exception as e:
        logger.error(f"Error triggering daily reports: {str(e)}")
        return {'success': False, 'error': str(e)}

def trigger_weekly_report_now():
    """Manually trigger weekly report generation"""
    try:
        logger.info("Manually triggering weekly reports")
        result = send_weekly_reports()
        return {'success': True, 'reports_sent': result}
        
    except Exception as e:
        logger.error(f"Error triggering weekly reports: {str(e)}")
        return {'success': False, 'error': str(e)}

def trigger_pending_expenses_cleanup_now():
    """Manually trigger pending expenses cleanup for testing"""
    try:
        logger.info("Manually triggering pending expenses cleanup")
        result = run_pending_expenses_cleanup()
        return result
        
    except Exception as e:
        logger.error(f"Error triggering pending expenses cleanup: {str(e)}")
        return {'success': False, 'error': str(e)}

def get_pending_expenses_cleanup_stats():
    """Get current pending expenses statistics"""
    try:
        from utils.pending_expenses_cleanup import pending_expenses_cleanup
        from app import app
        
        with app.app_context():
            return pending_expenses_cleanup.get_pending_expenses_stats()
        
    except Exception as e:
        logger.error(f"Error getting pending expenses stats: {str(e)}")
        return {'error': str(e)}
