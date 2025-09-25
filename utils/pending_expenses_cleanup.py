"""
Automated TTL cleanup mechanism for pending_expenses table
Prevents database bloat by removing expired clarification entries
"""
import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class PendingExpensesCleanup:
    """Handles automated cleanup of expired pending expenses"""
    
    def __init__(self):
        self.cleanup_batch_size = 1000  # Process in batches to avoid lock contention
        self.max_cleanup_time_seconds = 30  # Maximum time to spend on cleanup
        
    def cleanup_expired_entries(self) -> dict:
        """
        Remove expired entries from pending_expenses table
        
        Returns:
            Dict with cleanup statistics
        """
        from db_base import db
        
        cleanup_start = time.time()
        total_deleted = 0
        batches_processed = 0
        errors = []
        
        try:
            logger.info("Starting pending_expenses TTL cleanup...")
            
            # Use raw SQL for efficient bulk deletion with proper timezone handling
            cleanup_query = text("""
                DELETE FROM pending_expenses 
                WHERE pending_id IN (
                    SELECT pending_id FROM (
                        SELECT pending_id 
                        FROM pending_expenses 
                        WHERE expires_at < NOW() AT TIME ZONE 'UTC'
                        ORDER BY expires_at ASC
                        LIMIT :batch_size
                    ) AS expired_batch
                )
            """)
            
            while True:
                # Check if we've exceeded maximum cleanup time
                if time.time() - cleanup_start > self.max_cleanup_time_seconds:
                    logger.warning(f"Cleanup time limit reached ({self.max_cleanup_time_seconds}s), stopping")
                    break
                
                try:
                    # Execute deletion in batch
                    result = db.session.execute(cleanup_query, {'batch_size': self.cleanup_batch_size})
                    deleted_count = getattr(result, 'rowcount', 0)
                    
                    if deleted_count == 0:
                        # No more expired entries to delete
                        break
                    
                    # Commit the batch
                    db.session.commit()
                    
                    total_deleted += deleted_count
                    batches_processed += 1
                    
                    logger.info(f"Cleanup batch {batches_processed}: deleted {deleted_count} expired entries")
                    
                    # Small delay to avoid overwhelming the database
                    time.sleep(0.1)
                    
                except SQLAlchemyError as e:
                    logger.error(f"Database error during cleanup batch {batches_processed + 1}: {e}")
                    db.session.rollback()
                    errors.append(str(e))
                    break
                    
                except Exception as e:
                    logger.error(f"Unexpected error during cleanup batch {batches_processed + 1}: {e}")
                    db.session.rollback()
                    errors.append(str(e))
                    break
            
            cleanup_duration = time.time() - cleanup_start
            
            # Log cleanup summary
            if total_deleted > 0:
                logger.info(f"Cleanup completed: {total_deleted} expired entries removed in {cleanup_duration:.2f}s ({batches_processed} batches)")
            else:
                logger.debug(f"Cleanup completed: no expired entries found (checked in {cleanup_duration:.2f}s)")
            
            return {
                'success': True,
                'total_deleted': total_deleted,
                'batches_processed': batches_processed,
                'duration_seconds': round(cleanup_duration, 2),
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Critical error during pending_expenses cleanup: {e}")
            try:
                db.session.rollback()
            except:
                pass
            
            return {
                'success': False,
                'total_deleted': total_deleted,
                'batches_processed': batches_processed,
                'duration_seconds': round(time.time() - cleanup_start, 2),
                'errors': errors + [str(e)]
            }
    
    def get_pending_expenses_stats(self) -> dict:
        """
        Get statistics about pending expenses table for monitoring
        
        Returns:
            Dict with table statistics
        """
        from db_base import db
        
        try:
            # Query for table statistics
            stats_query = text("""
                SELECT 
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN expires_at < NOW() AT TIME ZONE 'UTC' THEN 1 END) as expired_entries,
                    COUNT(CASE WHEN expires_at >= NOW() AT TIME ZONE 'UTC' THEN 1 END) as active_entries,
                    MIN(created_at) as oldest_entry,
                    MAX(created_at) as newest_entry,
                    MIN(expires_at) as earliest_expiry,
                    MAX(expires_at) as latest_expiry
                FROM pending_expenses
            """)
            
            result = db.session.execute(stats_query).fetchone()
            
            if result:
                return {
                    'total_entries': result.total_entries or 0,
                    'expired_entries': result.expired_entries or 0,
                    'active_entries': result.active_entries or 0,
                    'oldest_entry': result.oldest_entry.isoformat() if result.oldest_entry else None,
                    'newest_entry': result.newest_entry.isoformat() if result.newest_entry else None,
                    'earliest_expiry': result.earliest_expiry.isoformat() if result.earliest_expiry else None,
                    'latest_expiry': result.latest_expiry.isoformat() if result.latest_expiry else None
                }
            else:
                return {
                    'total_entries': 0,
                    'expired_entries': 0,
                    'active_entries': 0,
                    'oldest_entry': None,
                    'newest_entry': None,
                    'earliest_expiry': None,
                    'latest_expiry': None
                }
                
        except Exception as e:
            logger.error(f"Error getting pending_expenses statistics: {e}")
            return {
                'error': str(e),
                'total_entries': 0,
                'expired_entries': 0,
                'active_entries': 0
            }

# Global instance for use by scheduler
pending_expenses_cleanup = PendingExpensesCleanup()

def run_pending_expenses_cleanup():
    """
    Main cleanup function for use by scheduler
    Handles application context and error recovery
    """
    from app import app
    
    try:
        with app.app_context():
            result = pending_expenses_cleanup.cleanup_expired_entries()
            
            # Log summary for monitoring
            if result['success']:
                if result['total_deleted'] > 0:
                    logger.info(f"Scheduled cleanup: removed {result['total_deleted']} expired pending expenses")
                else:
                    logger.debug("Scheduled cleanup: no expired entries to remove")
            else:
                logger.error(f"Scheduled cleanup failed: {result.get('errors', ['Unknown error'])}")
            
            return result
            
    except Exception as e:
        logger.error(f"Critical error in scheduled pending_expenses cleanup: {e}")
        return {
            'success': False,
            'total_deleted': 0,
            'batches_processed': 0,
            'duration_seconds': 0,
            'errors': [str(e)]
        }

def get_cleanup_stats():
    """
    Get pending expenses statistics for monitoring
    Handles application context
    """
    from app import app
    
    try:
        with app.app_context():
            return pending_expenses_cleanup.get_pending_expenses_stats()
            
    except Exception as e:
        logger.error(f"Error getting pending_expenses stats: {e}")
        return {
            'error': str(e),
            'total_entries': 0,
            'expired_entries': 0,
            'active_entries': 0
        }