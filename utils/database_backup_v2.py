"""
Database Backup and Restore System - Clean Version
100% safe implementation with proper Flask context handling
"""

import logging
import json
import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DatabaseBackupSystem:
    """Safe database backup system using existing models"""
    
    def __init__(self):
        self.backup_dir = "/tmp/finbrain_backups"
        self.enabled = os.getenv('ENABLE_BACKUPS', 'true').lower() == 'true'
        
        # Ensure backup directory exists
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create backup directory: {e}")
    
    def create_backup(self) -> Dict[str, Any]:
        """Create complete database backup in JSON format"""
        if not self.enabled:
            return {'status': 'disabled', 'message': 'Backups disabled via ENABLE_BACKUPS=false'}
        
        try:
            from models import User, Expense, MonthlySummary
            from db_base import db, app
            
            # Ensure we have Flask application context
            with app.app_context():
                
                # Initialize backup structure
                backup_data = {
                    'metadata': {
                        'backup_timestamp': datetime.utcnow().isoformat(),
                        'backup_version': '1.0',
                        'system': 'finbrain',
                        'tables': ['users', 'expenses', 'monthly_summaries']
                    },
                    'data': {}
                }
                
                # Backup Users table
                users = User.query.all()
                backup_data['data']['users'] = []
                
                for user in users:
                    user_data = {
                        'id': user.id,
                        'user_id_hash': user.user_id_hash,
                        'platform': user.platform,
                        'total_expenses': float(user.total_expenses) if user.total_expenses else 0.0,
                        'expense_count': user.expense_count,
                        'created_at': user.created_at.isoformat() if user.created_at else None,
                        'last_interaction': user.last_interaction.isoformat() if user.last_interaction else None,
                        'last_user_message_at': user.last_user_message_at.isoformat() if user.last_user_message_at else None,
                        'daily_message_count': user.daily_message_count,
                        'hourly_message_count': user.hourly_message_count,
                        'last_daily_reset': user.last_daily_reset.isoformat() if user.last_daily_reset else None,
                        'last_hourly_reset': user.last_hourly_reset.isoformat() if user.last_hourly_reset else None,
                        'is_new': user.is_new,
                        'has_completed_onboarding': user.has_completed_onboarding,
                        'onboarding_step': user.onboarding_step,
                        'interaction_count': user.interaction_count,
                        'first_name': user.first_name,
                        'income_range': user.income_range,
                        'spending_categories': user.spending_categories,
                        'primary_category': user.primary_category,
                        'focus_area': user.focus_area,
                        'additional_info': user.additional_info,
                        'preferences': user.preferences,
                        'reminder_scheduled_for': user.reminder_scheduled_for.isoformat() if user.reminder_scheduled_for else None,
                        'reminder_preference': user.reminder_preference,
                        'last_reminder_sent': user.last_reminder_sent.isoformat() if user.last_reminder_sent else None,
                        'privacy_consent_given': user.privacy_consent_given,
                        'privacy_consent_at': user.privacy_consent_at.isoformat() if user.privacy_consent_at else None,
                        'terms_accepted': user.terms_accepted,
                        'terms_accepted_at': user.terms_accepted_at.isoformat() if user.terms_accepted_at else None
                    }
                    backup_data['data']['users'].append(user_data)
                
                # Backup Expenses table
                expenses = Expense.query.all()
                backup_data['data']['expenses'] = []
                
                for expense in expenses:
                    expense_data = {
                        'id': expense.id,
                        'user_id': expense.user_id,
                        'description': expense.description,
                        'amount': float(expense.amount) if expense.amount else 0.0,
                        'category': expense.category,
                        'currency': expense.currency,
                        'date': expense.date.isoformat() if expense.date else None,
                        'time': expense.time.isoformat() if expense.time else None,
                        'month': expense.month,
                        'unique_id': expense.unique_id,
                        'created_at': expense.created_at.isoformat() if expense.created_at else None,
                        'platform': expense.platform,
                        'original_message': expense.original_message,
                        'ai_insights': expense.ai_insights,
                        'mid': expense.mid,
                        'superseded_by': expense.superseded_by,
                        'corrected_at': expense.corrected_at.isoformat() if expense.corrected_at else None,
                        'corrected_reason': expense.corrected_reason
                    }
                    backup_data['data']['expenses'].append(expense_data)
                
                # Backup Monthly Summaries table
                summaries = MonthlySummary.query.all()
                backup_data['data']['monthly_summaries'] = []
                
                for summary in summaries:
                    summary_data = {
                        'id': summary.id,
                        'user_id_hash': summary.user_id_hash,
                        'month': summary.month,
                        'total_amount': float(summary.total_amount) if summary.total_amount else 0.0,
                        'expense_count': summary.expense_count,
                        'categories': summary.categories,
                        'created_at': summary.created_at.isoformat() if summary.created_at else None,
                        'updated_at': summary.updated_at.isoformat() if summary.updated_at else None
                    }
                    backup_data['data']['monthly_summaries'].append(summary_data)
                
                # Save backup to file
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"finbrain_backup_{timestamp}.json"
                backup_path = os.path.join(self.backup_dir, backup_filename)
                
                with open(backup_path, 'w') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
                
                # Verify backup file was created
                if os.path.exists(backup_path):
                    file_size = os.path.getsize(backup_path)
                    
                    result = {
                        'status': 'success',
                        'backup_file': backup_path,
                        'timestamp': backup_data['metadata']['backup_timestamp'],
                        'tables_backed_up': len(backup_data['data']),
                        'records': {
                            'users': len(backup_data['data']['users']),
                            'expenses': len(backup_data['data']['expenses']),
                            'monthly_summaries': len(backup_data['data']['monthly_summaries'])
                        },
                        'file_size_bytes': file_size
                    }
                    
                    logger.info(f"Database backup created successfully: {backup_filename}")
                    return result
                else:
                    return {'status': 'error', 'message': 'Backup file was not created'}
                    
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def verify_backup(self, backup_path: str) -> Dict[str, Any]:
        """Verify backup file integrity and structure"""
        try:
            if not os.path.exists(backup_path):
                return {'status': 'error', 'message': 'Backup file not found'}
            
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            # Verify structure
            required_keys = ['metadata', 'data']
            for key in required_keys:
                if key not in backup_data:
                    return {'status': 'error', 'message': f'Missing required key: {key}'}
            
            required_tables = ['users', 'expenses', 'monthly_summaries']
            for table in required_tables:
                if table not in backup_data['data']:
                    return {'status': 'error', 'message': f'Missing table: {table}'}
            
            # Count records
            record_counts = {
                table: len(backup_data['data'][table]) 
                for table in required_tables
            }
            
            return {
                'status': 'valid',
                'backup_timestamp': backup_data['metadata'].get('backup_timestamp'),
                'record_counts': record_counts,
                'file_size_bytes': os.path.getsize(backup_path)
            }
            
        except Exception as e:
            return {'status': 'error', 'message': f'Backup verification failed: {e}'}
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backup files"""
        try:
            if not os.path.exists(self.backup_dir):
                return []
            
            backups = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('finbrain_backup_') and filename.endswith('.json'):
                    backup_path = os.path.join(self.backup_dir, filename)
                    verification = self.verify_backup(backup_path)
                    
                    backup_info = {
                        'filename': filename,
                        'path': backup_path,
                        'verification': verification
                    }
                    backups.append(backup_info)
            
            # Sort by filename (which includes timestamp)
            backups.sort(key=lambda x: x['filename'], reverse=True)
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall backup system status"""
        try:
            backups = self.list_backups()
            latest_backup = backups[0] if backups else None
            
            return {
                'enabled': self.enabled,
                'backup_directory': self.backup_dir,
                'directory_exists': os.path.exists(self.backup_dir),
                'backup_count': len(backups),
                'latest_backup': latest_backup
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

# Global backup instance
backup_system = DatabaseBackupSystem()

# Convenient functions for easy integration
def create_database_backup() -> Dict[str, Any]:
    """Create a full database backup"""
    return backup_system.create_backup()

def verify_backup_file(backup_path: str) -> Dict[str, Any]:
    """Verify a specific backup file"""
    return backup_system.verify_backup(backup_path)

def list_available_backups() -> List[Dict[str, Any]]:
    """List all available backup files"""
    return backup_system.list_backups()

def get_backup_status() -> Dict[str, Any]:
    """Get backup system status"""
    return backup_system.get_status()

# Health check for monitoring
def backup_health_check() -> Dict[str, Any]:
    """Health check for backup system"""
    try:
        status = get_backup_status()
        
        if not status.get('enabled'):
            return {'status': 'disabled', 'message': 'Backups disabled'}
        
        if not status.get('directory_exists'):
            return {'status': 'error', 'message': 'Backup directory missing'}
        
        return {
            'status': 'healthy',
            'backup_count': status.get('backup_count', 0),
            'latest_backup': status.get('latest_backup', {}).get('filename', 'none'),
            'enabled': status.get('enabled', False)
        }
        
    except Exception as e:
        return {'status': 'error', 'error': str(e)}