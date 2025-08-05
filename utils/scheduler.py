"""Task scheduling for automated reports"""
import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.report_generator import send_daily_reports, send_weekly_reports

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
        
        # Start the scheduler
        scheduler.start()
        logger.info("Scheduler initialized successfully")
        
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
